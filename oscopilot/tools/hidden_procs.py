"""可疑进程检测：按三层架构识别 Linux 下通过 ps/top 看不到的隐藏进程与 Rootkit 行为。

架构参考 `进程隐藏研究.md`，分三层：

第一层 —— 进程发现
    三源 PID 对比（/proc getdents64 vs psutil vs ps），识别用户态 rootkit 隐藏。

第二层 —— 隐藏检测
    - 内核模块隐藏（lsmod vs /sys/module vs /proc/modules）
    - LD_PRELOAD 用户态 rootkit（/etc/ld.so.preload + 环境变量）
    - PID namespace 异常（NSpid 多层映射）
    - ptrace 注入（TracerPid 非零）
    - socket 隐藏（/proc/net/tcp vs netstat）

第三层 —— 行为检测
    - exe 已删除（内存驻留木马）
    - 匿名可执行内存（maps 中 rwxp 且无 pathname）
    - 伪装进程名（exe basename 与 argv[0] 不符）
    - 异常父子关系（如 nginx 子进程是 bash/chmod）
    - cmdline 为空但非内核线程
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import psutil

from ..auditing import AuditEvent, now_iso
from ..context import AppContext
from ..policy import Operation
from ..utils import generate_action_id


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class ProcessInfo:
    """单个进程的关键信息。"""

    pid: int
    comm: str = ""  # /proc/[pid]/comm，内核态进程名（≤15 字符）
    cmdline: str = ""  # /proc/[pid]/cmdline，空格连接
    exe: str = ""  # /proc/[pid]/exe 软链接目标
    exe_deleted: bool = False  # exe 是否已被删除
    state: str = ""  # /proc/[pid]/status 中的 State 行
    uid: Optional[int] = None
    ppid: Optional[int] = None
    tracer_pid: Optional[int] = None  # ptrace 注入检测用
    nspid: str = ""  # /proc/[pid]/status 中的 NSpid 行
    seen_in: List[str] = field(default_factory=list)  # 在哪些来源中出现

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 第一层：进程发现（三源 PID 对比）
# ---------------------------------------------------------------------------


def _list_proc_pids() -> List[int]:
    """通过 os.listdir 直接遍历 /proc（走 getdents64 系统调用，最难被绕过）。"""
    pids: List[int] = []
    try:
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                pids.append(int(entry))
    except OSError:
        pass
    return pids


def _list_psutil_pids() -> List[int]:
    """通过 psutil 获取 PID 列表（走 libc readdir，可能被 hook）。"""
    try:
        return [p.pid for p in psutil.process_iter(attrs=["pid"])]
    except Exception:
        return []


def _list_ps_pids() -> List[int]:
    """通过 `ps -eo pid=` 子进程获取 PID 列表（走 libc + procps，最易被 hook）。"""
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid=", "--no-headers"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            return []
        return [
            int(line.strip())
            for line in proc.stdout.splitlines()
            if line.strip().isdigit()
        ]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


# ---------------------------------------------------------------------------
# /proc 信息读取
# ---------------------------------------------------------------------------


def _read_proc_info(pid: int) -> ProcessInfo:
    """读取 /proc/[pid] 下的关键信息，权限不足时返回部分字段。"""
    info = ProcessInfo(pid=pid)
    base = Path("/proc") / str(pid)

    # comm
    try:
        info.comm = (base / "comm").read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        pass

    # cmdline（以 \0 分隔）
    try:
        raw = (base / "cmdline").read_bytes()
        parts = [p.decode("utf-8", errors="ignore") for p in raw.split(b"\0") if p]
        info.cmdline = " ".join(parts)
    except OSError:
        pass

    # exe 软链接
    try:
        target = os.readlink(str(base / "exe"))
        info.exe = target
        if "(deleted)" in target:
            info.exe_deleted = True
    except OSError:
        pass

    # status -> state / uid / ppid / tracer_pid / nspid
    try:
        for line in (base / "status").read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("State:"):
                info.state = line.split(":", 1)[1].strip()
            elif line.startswith("Uid:"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        info.uid = int(parts[1])
                    except ValueError:
                        pass
            elif line.startswith("PPid:"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        info.ppid = int(parts[1])
                    except ValueError:
                        pass
            elif line.startswith("TracerPid:"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        info.tracer_pid = int(parts[1])
                    except ValueError:
                        pass
            elif line.startswith("NSpid:"):
                info.nspid = line.split(":", 1)[1].strip()
    except OSError:
        pass

    return info


def _is_kernel_thread(info: ProcessInfo) -> bool:
    """判断是否为内核线程：cmdline 为空且无 exe 链接。"""
    return not info.cmdline and not info.exe


# ---------------------------------------------------------------------------
# 第二层：隐藏检测
# ---------------------------------------------------------------------------


# --- 2.1 内核模块隐藏 ---


def _list_lsmod_modules() -> Set[str]:
    """通过 lsmod 获取已加载模块列表（走 /proc/modules，可能被 hook）。"""
    try:
        proc = subprocess.run(
            ["lsmod"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            return set()
        # 第一行是表头，后续每行第一列是模块名
        modules: Set[str] = set()
        for line in proc.stdout.splitlines()[1:]:
            parts = line.split()
            if parts:
                modules.add(parts[0])
        return modules
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()


def _list_proc_modules() -> Set[str]:
    """直接读取 /proc/modules（与 lsmod 同源但路径不同，可做交叉验证）。"""
    try:
        content = Path("/proc/modules").read_text(encoding="utf-8", errors="ignore")
        modules: Set[str] = set()
        for line in content.splitlines():
            parts = line.split()
            if parts:
                modules.add(parts[0])
        return modules
    except OSError:
        return set()


def _list_sys_modules() -> Set[str]:
    """遍历 /sys/module 获取已加载模块（走 sysfs，独立于 procfs）。"""
    try:
        return {entry for entry in os.listdir("/sys/module") if not entry.startswith(".")}
    except OSError:
        return set()


def detect_hidden_modules() -> Dict[str, Any]:
    """检测内核模块隐藏：三源对比 lsmod / /proc/modules / /sys/module。

    /sys/module 中存在但 lsmod / /proc/modules 中看不到的模块 = 隐藏模块候选。
    """
    lsmod = _list_lsmod_modules()
    proc_mods = _list_proc_modules()
    sys_mods = _list_sys_modules()

    # /sys/module 是最底层来源（sysfs），lsmod 和 /proc/modules 都走 procfs
    procfs_mods = lsmod | proc_mods
    hidden = sorted(sys_mods - procfs_mods)

    return {
        "lsmod_count": len(lsmod),
        "proc_modules_count": len(proc_mods),
        "sys_module_count": len(sys_mods),
        "hidden_modules": hidden,
        "has_finding": len(hidden) > 0,
    }


# --- 2.2 LD_PRELOAD 用户态 rootkit ---


def detect_ld_preload() -> Dict[str, Any]:
    """检测 LD_PRELOAD 用户态 rootkit。

    检查 /etc/ld.so.preload 和环境变量 LD_PRELOAD 中是否存在非系统库。
    """
    findings: List[Dict[str, Any]] = []

    # /etc/ld.so.preload
    preload_file = Path("/etc/ld.so.preload")
    preload_entries: List[str] = []
    if preload_file.exists():
        try:
            content = preload_file.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    preload_entries.append(line)
            if preload_entries:
                findings.append(
                    {
                        "source": "/etc/ld.so.preload",
                        "entries": preload_entries,
                        "risk": "high",
                        "reason": "/etc/ld.so.preload 非空，所有动态程序将加载指定 so",
                    }
                )
        except OSError:
            pass

    # 环境变量 LD_PRELOAD
    env_preload = os.environ.get("LD_PRELOAD", "")
    if env_preload:
        entries = [e.strip() for e in env_preload.split(":") if e.strip()]
        if entries:
            findings.append(
                {
                    "source": "env:LD_PRELOAD",
                    "entries": entries,
                    "risk": "medium",
                    "reason": "环境变量 LD_PRELOAD 已设置，仅影响当前进程树",
                }
            )

    return {
        "findings": findings,
        "has_finding": len(findings) > 0,
    }


# --- 2.3 PID namespace 异常 ---


def _parse_nspid(nspid_str: str) -> List[int]:
    """解析 NSpid 字段，返回各级 namespace 中的 PID。

    例如 "NSpid: 1 5000" 返回 [1, 5000]，表示在当前 namespace 是 PID 1，
    在父 namespace 是 PID 5000（容器内典型）。
    """
    parts = nspid_str.split()
    try:
        return [int(p) for p in parts]
    except ValueError:
        return []


def detect_namespace_anomalies(pids: List[int]) -> List[Dict[str, Any]]:
    """检测 PID namespace 异常：NSpid 多层映射（容器或 namespace 隔离）。"""
    anomalies: List[Dict[str, Any]] = []
    for pid in pids:
        info = _read_proc_info(pid)
        if not info.nspid:
            continue
        nspid_list = _parse_nspid(info.nspid)
        # 多层 NSpid 表示在子 namespace 中运行（容器/隔离环境）
        if len(nspid_list) > 1:
            anomalies.append(
                {
                    "pid": pid,
                    "comm": info.comm,
                    "nspid": info.nspid,
                    "nspid_levels": len(nspid_list),
                    "reason": f"存在 {len(nspid_list)} 层 PID namespace 映射（可能为容器或隔离环境）",
                }
            )
    return anomalies


# --- 2.4 ptrace 注入 ---


def detect_ptrace_injections(pids: List[int]) -> List[Dict[str, Any]]:
    """检测 ptrace 注入：TracerPid 非零表示进程正被调试/注入。"""
    injections: List[Dict[str, Any]] = []
    for pid in pids:
        info = _read_proc_info(pid)
        if info.tracer_pid and info.tracer_pid > 0:
            injections.append(
                {
                    "pid": pid,
                    "comm": info.comm,
                    "tracer_pid": info.tracer_pid,
                    "reason": f"进程被 TracerPid={info.tracer_pid} 调试/注入（非调试场景下高度可疑）",
                }
            )
    return injections


# --- 2.5 socket 隐藏 ---


def _parse_proc_net_tcp() -> Dict[str, Dict[str, Any]]:
    """解析 /proc/net/tcp 和 /proc/net/tcp6，返回 inode → 连接信息映射。"""
    sockets: Dict[str, Dict[str, Any]] = {}
    for path in ["/proc/net/tcp", "/proc/net/tcp6"]:
        try:
            content = Path(path).read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines()[1:]:  # 跳过表头
                parts = line.split()
                if len(parts) >= 10:
                    local_addr = parts[1]
                    remote_addr = parts[2]
                    state = parts[3]
                    inode = parts[9]
                    sockets[inode] = {
                        "local": local_addr,
                        "remote": remote_addr,
                        "state": state,
                        "protocol": "tcp6" if "6" in path else "tcp",
                    }
        except OSError:
            pass
    return sockets


def _list_netstat_tcp() -> Set[str]:
    """通过 netstat 获取 TCP 连接的 inode 集合（可被 hook）。"""
    try:
        proc = subprocess.run(
            ["netstat", "-tlnp", "--program"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            return set()
        # netstat 不直接输出 inode，但可通过 /proc/[pid]/fd 反查
        # 这里简化处理：返回空集，让对比逻辑退化为"只看 /proc/net/tcp"
        return set()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()


def _find_socket_owners(socket_inodes: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """遍历 /proc/[pid]/fd，找到每个 socket inode 的归属进程。"""
    owners: Dict[str, int] = {}
    for pid_str in os.listdir("/proc"):
        if not pid_str.isdigit():
            continue
        fd_dir = Path("/proc") / pid_str / "fd"
        try:
            for fd in os.listdir(str(fd_dir)):
                try:
                    target = os.readlink(str(fd_dir / fd))
                    # socket:[12345]
                    if target.startswith("socket:["):
                        inode = target[8:-1]  # 去掉 "socket:[" 和 "]"
                        if inode in socket_inodes:
                            owners[inode] = int(pid_str)
                except OSError:
                    continue
        except OSError:
            continue
    return owners


def detect_socket_hiding() -> Dict[str, Any]:
    """检测 socket 隐藏：对比 /proc/net/tcp 与进程 fd 关联。

    /proc/net/tcp 中存在但无进程关联的 socket 可能被隐藏（rootkit 隐藏监听端口）。
    """
    socket_inodes = _parse_proc_net_tcp()
    if not socket_inodes:
        return {"total_sockets": 0, "orphan_sockets": [], "has_finding": False}

    owners = _find_socket_owners(socket_inodes)
    orphan_inodes = sorted(set(socket_inodes.keys()) - set(owners.keys()))

    orphan_sockets: List[Dict[str, Any]] = []
    for inode in orphan_inodes:
        sock = socket_inodes[inode]
        orphan_sockets.append(
            {
                "inode": inode,
                "local": sock["local"],
                "remote": sock["remote"],
                "state": sock["state"],
                "protocol": sock["protocol"],
                "reason": "socket 在 /proc/net/tcp 中存在但无进程 fd 关联（可能被隐藏）",
            }
        )

    return {
        "total_sockets": len(socket_inodes),
        "orphan_count": len(orphan_sockets),
        "orphan_sockets": orphan_sockets,
        "has_finding": len(orphan_sockets) > 0,
    }


# ---------------------------------------------------------------------------
# 第三层：行为检测
# ---------------------------------------------------------------------------


# --- 3.1 匿名可执行内存（内存驻留木马） ---


# 匹配 /proc/[pid]/maps 中的匿名可执行段：rwxp 且 pathname 为空或 [heap]
_ANON_RWX_RE = re.compile(r"^[0-9a-f]+-[0-9a-f]+ (rwx)p .* (\[heap\]|\[stack\])?\s*$")


def _check_anon_rwx(pid: int) -> List[Dict[str, Any]]:
    """检查 /proc/[pid]/maps 中是否存在匿名可执行内存段（rwxp 且无 pathname）。"""
    findings: List[Dict[str, Any]] = []
    maps_path = Path("/proc") / str(pid) / "maps"
    try:
        for line in maps_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split(None, 5)
            if len(parts) < 5:
                continue
            perms = parts[1]
            pathname = parts[5] if len(parts) >= 6 else ""
            # rwxp 且 pathname 为空（匿名可执行内存）
            if perms == "rwxp" and not pathname.strip():
                findings.append(
                    {
                        "address": parts[0],
                        "perms": perms,
                        "reason": "匿名可执行内存段（rwxp 且无 pathname，可能是内存驻留木马）",
                    }
                )
    except OSError:
        pass
    return findings


# --- 3.2 伪装进程名 ---


def _check_disguised_name(info: ProcessInfo) -> Optional[str]:
    """检查 exe basename 与 argv[0] 是否不符（伪装进程名）。"""
    if not info.exe or info.exe_deleted:
        return None
    try:
        exe_basename = os.path.basename(info.exe)
    except (ValueError, OSError):
        return None
    if not exe_basename or not info.cmdline:
        return None
    # 取 argv[0] 的 basename
    argv0 = info.cmdline.split()[0]
    argv0_basename = os.path.basename(argv0)
    if exe_basename != argv0_basename:
        return (
            f"exe basename({exe_basename!r}) 与 argv[0] basename({argv0_basename!r}) 不符"
        )
    return None


# --- 3.3 异常父子关系 ---


# 已知合理的父进程白名单（父 comm → 允许的子 comm 前缀）
# 仅检测明确异常的模式，避免误报
_SUSPICIOUS_PARENT_CHILD = {
    # 父进程是 Web 服务器/数据库，子进程不应该是 shell
    "nginx": {"bash", "sh", "zsh", "dash", "chmod", "curl", "wget", "python"},
    "httpd": {"bash", "sh", "zsh", "dash", "chmod", "curl", "wget", "python"},
    "mysqld": {"bash", "sh", "zsh", "dash", "chmod", "curl", "wget", "python"},
    "redis-server": {"bash", "sh", "zsh", "dash", "chmod", "curl", "wget", "python"},
}


def _build_process_tree(pids: List[int]) -> Dict[int, ProcessInfo]:
    """构建 PID → ProcessInfo 映射。"""
    tree: Dict[int, ProcessInfo] = {}
    for pid in pids:
        tree[pid] = _read_proc_info(pid)
    return tree


def _check_parent_child_anomaly(info: ProcessInfo, tree: Dict[int, ProcessInfo]) -> Optional[str]:
    """检查异常父子关系（如 nginx 的子进程是 bash）。"""
    if info.ppid is None or info.ppid not in tree:
        return None
    parent = tree[info.ppid]
    parent_comm = parent.comm
    child_comm = info.comm

    suspicious_children = _SUSPICIOUS_PARENT_CHILD.get(parent_comm)
    if suspicious_children and child_comm in suspicious_children:
        return (
            f"异常父子关系: 父进程 {parent_comm}(pid={info.ppid}) "
            f"的子进程是 {child_comm}(pid={info.pid})"
        )
    return None


# --- 3.4 综合可疑进程扫描 ---


def _check_suspicious_features(info: ProcessInfo) -> List[str]:
    """检查单个进程的可疑特征（不含父子关系和内存扫描，这两项需要额外上下文）。"""
    reasons: List[str] = []

    if _is_kernel_thread(info):
        return reasons

    # exe 已删除
    if info.exe_deleted:
        reasons.append("exe 已删除（可执行文件被删除但仍运行，可能是内存驻留木马）")

    # cmdline 为空但非内核线程
    if not info.cmdline:
        reasons.append("cmdline 为空但非内核线程")

    # comm 含异常字符
    if info.comm:
        if info.comm != info.comm.strip():
            reasons.append(f"comm 含首尾空格: {info.comm!r}")
        if ".." in info.comm:
            reasons.append(f"comm 含连续点号: {info.comm!r}")

    # 伪装进程名
    disguised = _check_disguised_name(info)
    if disguised:
        reasons.append(disguised)

    return reasons


def scan_suspicious_processes(
    pids: List[int],
    tree: Optional[Dict[int, ProcessInfo]] = None,
    check_maps: bool = True,
) -> List[Dict[str, Any]]:
    """扫描所有进程的可疑特征，返回带 reasons 的进程列表。

    Args:
        pids: 要扫描的 PID 列表。
        tree: 预构建的进程树（可选，避免重复读取）。
        check_maps: 是否检查 /proc/[pid]/maps（较慢，可关闭）。
    """
    if tree is None:
        tree = _build_process_tree(pids)

    suspicious: List[Dict[str, Any]] = []
    for pid in sorted(pids):
        info = tree.get(pid)
        if info is None:
            info = _read_proc_info(pid)

        reasons = _check_suspicious_features(info)

        # 父子关系异常
        parent_anomaly = _check_parent_child_anomaly(info, tree)
        if parent_anomaly:
            reasons.append(parent_anomaly)

        # 匿名可执行内存
        if check_maps and not _is_kernel_thread(info):
            anon_findings = _check_anon_rwx(pid)
            for f in anon_findings:
                reasons.append(f["reason"])

        if reasons:
            entry = info.to_dict()
            entry["reasons"] = reasons
            suspicious.append(entry)

    return suspicious


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def detect_hidden_processes(ctx: AppContext) -> Dict[str, Any]:
    """执行可疑进程检测，返回结构化报告。

    按三层架构实现：
      1. 进程发现：三源 PID 对比（/proc vs psutil vs ps）
      2. 隐藏检测：模块隐藏、LD_PRELOAD、namespace、ptrace、socket 隐藏
      3. 行为检测：exe deleted、匿名 rwx 内存、伪装进程名、异常父子关系

    所有检测均为只读操作，不修改系统状态，无需审批。

    Args:
        ctx: 应用上下文，用于策略评估与审计日志。

    Returns:
        包含各检测层结果的结构化报告字典。
    """
    op = Operation(type="shell", name="detect_hidden_procs", args={})
    decision = ctx.policy.evaluate(op)
    action_id = generate_action_id()

    if not decision.allowed:
        ctx.auditor.log_event(
            AuditEvent(
                timestamp=now_iso(),
                actor=ctx.actor,
                session_id=ctx.session_id,
                action_id=action_id,
                tool=op.name,
                args=op.args,
                result_summary=decision.reason,
                stdout="",
                stderr="",
                file_diff_hash=None,
                policy_decision="denied",
                approval_result="rejected",
            )
        )
        raise RuntimeError(f"策略拒绝: {decision.reason}")

    # === 第一层：进程发现 ===
    proc_pids = set(_list_proc_pids())
    psutil_pids = set(_list_psutil_pids())
    ps_pids = set(_list_ps_pids())

    sources: Dict[str, List[int]] = {
        "proc_getdents": sorted(proc_pids),
        "psutil": sorted(psutil_pids),
        "ps_command": sorted(ps_pids),
    }

    # 隐藏 = proc 看到 但 (psutil 或 ps) 看不到
    userland_pids = psutil_pids | ps_pids
    hidden_pids = sorted(proc_pids - userland_pids)

    # 隐藏进程详情
    hidden_details: List[Dict[str, Any]] = []
    for pid in hidden_pids:
        info = _read_proc_info(pid)
        seen: List[str] = ["proc_getdents"]
        if pid in psutil_pids:
            seen.append("psutil")
        if pid in ps_pids:
            seen.append("ps_command")
        info.seen_in = seen
        hidden_details.append(info.to_dict())

    all_pids = sorted(proc_pids)
    proc_tree = _build_process_tree(all_pids)

    # === 第二层：隐藏检测 ===
    hidden_modules = detect_hidden_modules()
    ld_preload = detect_ld_preload()
    namespace_anomalies = detect_namespace_anomalies(all_pids)
    ptrace_injections = detect_ptrace_injections(all_pids)
    socket_hiding = detect_socket_hiding()

    # === 第三层：行为检测 ===
    suspicious_processes = scan_suspicious_processes(
        all_pids, tree=proc_tree, check_maps=True
    )

    # === 汇总 ===
    finding_count = (
        len(hidden_pids)
        + len(hidden_modules["hidden_modules"])
        + len(ld_preload["findings"])
        + len(namespace_anomalies)
        + len(ptrace_injections)
        + len(socket_hiding.get("orphan_sockets", []))
        + len(suspicious_processes)
    )

    summary = (
        f"三层检测完成: "
        f"进程发现(三源 PID: proc={len(proc_pids)} psutil={len(psutil_pids)} ps={len(ps_pids)}); "
        f"隐藏进程: {len(hidden_pids)}; "
        f"隐藏模块: {len(hidden_modules['hidden_modules'])}; "
        f"LD_PRELOAD 异常: {len(ld_preload['findings'])}; "
        f"namespace 异常: {len(namespace_anomalies)}; "
        f"ptrace 注入: {len(ptrace_injections)}; "
        f"socket 隐藏: {len(socket_hiding.get('orphan_sockets', []))}; "
        f"可疑进程(行为层): {len(suspicious_processes)}; "
        f"总发现数: {finding_count}"
    )

    # 审计
    ctx.auditor.log_event(
        AuditEvent(
            timestamp=now_iso(),
            actor=ctx.actor,
            session_id=ctx.session_id,
            action_id=action_id,
            tool=op.name,
            args=op.args,
            result_summary=summary,
            stdout="",
            stderr="",
            file_diff_hash=None,
            policy_decision="allow",
            approval_result="n/a",
        )
    )

    return {
        "timestamp": now_iso(),
        "summary": summary,
        "total_findings": finding_count,
        # 第一层：进程发现
        "sources": sources,
        "hidden_pids": hidden_pids,
        "hidden_details": hidden_details,
        # 第二层：隐藏检测
        "hidden_modules": hidden_modules,
        "ld_preload": ld_preload,
        "namespace_anomalies": namespace_anomalies,
        "ptrace_injections": ptrace_injections,
        "socket_hiding": socket_hiding,
        # 第三层：行为检测
        "suspicious_processes": suspicious_processes,
    }

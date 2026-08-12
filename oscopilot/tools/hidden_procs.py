"""可疑进程检测：通过多源对比识别 ps/top 看不到的隐藏进程。

原理：
    用户态 rootkit 通常 hook libc 的 readdir/opendir，让 ps、top 等工具
    看不到特定 PID；但内核态的 getdents64 系统调用难以被绕过。

    本模块通过三种来源对比 PID 列表：
      1. `os.listdir("/proc")` —— 直接走 getdents64 系统调用，最底层
      2. `psutil.process_iter` —— 走 libc readdir，可能被 hook
      3. `ps -eo pid=` 子进程 —— 走 libc + procps 库，最易被 hook

    在源 1 中存在但在源 2/3 中缺失的 PID，即为隐藏进程候选。

除此之外还会扫描其他可疑特征：
    - exe 软链接指向 `(deleted)`：可执行文件被删除但仍运行
    - cmdline 为空但非内核线程
    - comm 含异常字符（如 `..`、首尾空格）
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from ..auditing import AuditEvent, now_iso
from ..context import AppContext
from ..policy import Operation
from ..utils import generate_action_id


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
    seen_in: List[str] = field(default_factory=list)  # 在哪些来源中出现

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _list_proc_pids() -> List[int]:
    """通过 os.listdir 直接遍历 /proc（走 getdents64 系统调用）。"""
    pids: List[int] = []
    try:
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                pids.append(int(entry))
    except OSError:
        pass
    return pids


def _list_psutil_pids() -> List[int]:
    """通过 psutil 获取 PID 列表（走 libc readdir）。"""
    try:
        return [p.pid for p in psutil.process_iter(attrs=["pid"])]
    except Exception:
        return []


def _list_ps_pids() -> List[int]:
    """通过 `ps -eo pid=` 子进程获取 PID 列表（走 libc + procps）。"""
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
        # 权限不足或进程已退出
        pass

    # status -> state / uid / ppid
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
    except OSError:
        pass

    return info


def _is_kernel_thread(info: ProcessInfo) -> bool:
    """判断是否为内核线程：cmdline 为空且无 exe 链接。"""
    return not info.cmdline and not info.exe


def _check_suspicious(info: ProcessInfo) -> List[str]:
    """检查单个进程的可疑特征，返回原因列表（空表示无可疑）。"""
    reasons: List[str] = []

    # 内核线程不做常规可疑检查
    if _is_kernel_thread(info):
        return reasons

    # exe 已删除
    if info.exe_deleted:
        reasons.append("exe 已删除（可执行文件被删除但仍运行）")

    # cmdline 为空但非内核线程（可能是 rootkit 占位或异常进程）
    if not info.cmdline:
        reasons.append("cmdline 为空但非内核线程")

    # comm 含异常字符
    if info.comm:
        if info.comm != info.comm.strip():
            reasons.append(f"comm 含首尾空格: {info.comm!r}")
        if ".." in info.comm:
            reasons.append(f"comm 含连续点号: {info.comm!r}")

    return reasons


def detect_hidden_processes(ctx: AppContext) -> Dict[str, Any]:
    """执行可疑进程检测，返回结构化报告。

    通过三源对比 PID 识别在 /proc 中存在但 psutil/ps 看不到的隐藏进程，
    并扫描其他可疑特征（exe 已删除、cmdline 异常等）。

    Args:
        ctx: 应用上下文，用于策略评估与审计日志。

    Returns:
        包含 sources / hidden_pids / hidden_details / suspicious_processes /
        summary 字段的报告字典。
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

    # 三源采集
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

    # 其他可疑进程扫描（遍历所有 /proc PID）
    suspicious: List[Dict[str, Any]] = []
    for pid in sorted(proc_pids):
        info = _read_proc_info(pid)
        reasons = _check_suspicious(info)
        if reasons:
            entry = info.to_dict()
            entry["reasons"] = reasons
            suspicious.append(entry)

    # 摘要
    summary = (
        f"三源 PID 数: proc={len(proc_pids)} psutil={len(psutil_pids)} ps={len(ps_pids)}; "
        f"疑似隐藏进程: {len(hidden_pids)}; "
        f"其他可疑进程: {len(suspicious)}"
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
        "sources": sources,
        "hidden_pids": hidden_pids,
        "hidden_details": hidden_details,
        "suspicious_processes": suspicious,
        "summary": summary,
    }

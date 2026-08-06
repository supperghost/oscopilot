"""crash 工具封装 - 用于加载 vmcore 并执行调试命令。

crash 是 Linux 内核官方推荐的 vmcore 分析工具，支持：
- 查看内核日志 (log)
- 查看调用栈 (bt)
- 查看进程状态 (ps)
- 查看寄存器 (regs)
- 解析结构体 (struct)
- 反汇编 (dis)
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional


class CrashRunnerError(Exception):
    """crash 执行错误。"""


@dataclass
class BacktraceInfo:
    """解析后的调用栈信息。"""
    raw_output: str
    frames: List[str]  # 每帧的简要描述
    panic_type: str = ""  # panic/oops/BUG
    panic_function: str = ""  # 崩溃发生的函数
    cpu_id: int = -1  # 崩溃发生的 CPU


@dataclass
class CrashEnvInfo:
    """环境检查结果。"""
    crash_available: bool
    vmcore_exists: bool
    vmlinux_exists: bool
    crash_version: str = ""
    vmcore_size: int = 0
    vmlinux_size: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @property
    def is_ready(self) -> bool:
        return self.crash_available and self.vmcore_exists and self.vmlinux_exists and len(self.errors) == 0


class CrashRunner:
    """crash 工具执行器。

    负责启动 crash 会话、执行命令、解析输出。
    支持 Mock 模式用于测试。
    """

    def __init__(
        self,
        vmcore_path: str,
        vmlinux_path: str,
        mock_mode: bool = False,
        mock_responses: Optional[Dict[str, str]] = None,
    ) -> None:
        self._vmcore_path = Path(vmcore_path)
        self._vmlinux_path = Path(vmlinux_path)
        self._mock_mode = mock_mode
        self._mock_responses = mock_responses or {}
        self._command_history: List[str] = []

    @property
    def is_available(self) -> bool:
        """检查 crash 工具是否可用。"""
        if self._mock_mode:
            return True
        return shutil.which("crash") is not None

    @property
    def vmcore_exists(self) -> bool:
        """检查 vmcore 文件是否存在。"""
        if self._mock_mode:
            return True
        return self._vmcore_path.is_file()

    @property
    def vmlinux_exists(self) -> bool:
        """检查 vmlinux 文件是否存在。"""
        if self._mock_mode:
            return True
        return self._vmlinux_path.is_file()

    @property
    def command_history(self) -> List[str]:
        """获取执行过的命令历史。"""
        return self._command_history.copy()

    def get_env_info(self) -> CrashEnvInfo:
        """获取完整的环境检查信息。"""
        info = CrashEnvInfo(
            crash_available=self.is_available,
            vmcore_exists=self.vmcore_exists,
            vmlinux_exists=self.vmlinux_exists,
        )

        # 获取 crash 版本
        if not self._mock_mode and self.is_available:
            try:
                proc = subprocess.run(
                    ["crash", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                info.crash_version = proc.stdout.strip() or proc.stderr.strip()
            except Exception:
                info.crash_version = "unknown"
        elif self._mock_mode:
            info.crash_version = "10.0 (mock)"

        # 获取文件大小
        if self.vmcore_exists and not self._mock_mode:
            info.vmcore_size = self._vmcore_path.stat().st_size
        if self.vmlinux_exists and not self._mock_mode:
            info.vmlinux_size = self._vmlinux_path.stat().st_size

        # 收集错误
        if not self.is_available:
            info.errors.append("crash 工具未安装或不在 PATH 中")
        if not self.vmcore_exists:
            info.errors.append(f"vmcore 文件不存在: {self._vmcore_path}")
        if not self.vmlinux_exists:
            info.errors.append(f"vmlinux 文件不存在: {self._vmlinux_path}")

        return info

    def validate(self) -> List[str]:
        """验证环境，返回错误信息列表。"""
        return self.get_env_info().errors

    def execute(self, command: str, timeout: int = 30) -> str:
        """在 crash 会话中执行命令并返回输出。

        Args:
            command: crash 命令，如 "bt", "log", "ps" 等
            timeout: 超时时间（秒）

        Returns:
            命令输出字符串

        Raises:
            CrashRunnerError: 执行失败时抛出
        """
        self._command_history.append(command)

        # Mock 模式
        if self._mock_mode:
            return self._mock_responses.get(command, self._get_default_mock_response(command))

        errors = self.validate()
        if errors:
            raise CrashRunnerError("环境检查失败: " + "; ".join(errors))

        # 构建 crash 命令：crash vmcore vmlinux -c "<command>"
        cmd = [
            "crash",
            str(self._vmcore_path),
            str(self._vmlinux_path),
            "-c",
            command,
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
            )

            output = proc.stdout
            if proc.returncode != 0:
                if "ERROR" in output or "error" in output.lower():
                    raise CrashRunnerError(f"crash 命令执行失败: {output.strip()}")

            return output.strip()

        except subprocess.TimeoutExpired:
            raise CrashRunnerError(f"crash 命令超时（{timeout}秒）: {command}")
        except FileNotFoundError:
            raise CrashRunnerError("crash 工具未找到")
        except Exception as e:
            raise CrashRunnerError(f"crash 执行异常: {e}")

    def _get_default_mock_response(self, command: str) -> str:
        """获取默认的 Mock 响应。"""
        cmd_lower = command.lower().split()[0] if command else ""

        mock_responses = {
            "bt": "PID  TASK  CPU  COMM  STATE\n1234  ffff8880abc0  0  crash  RUNNING\n\ncrash 命令: dump_stack+0x5e/0x70\nCPU: 0 PID: 1234 Comm: crash Not tainted 5.15.0-...\nCall Trace:\n dump_stack+0x5e/0x70\n panic+0x11b/0x2b0\n sysrq_timer+0x4e/0x60\n sysrq_timer_func+0x10/0x30\n",
            "log": "[  12.345678] BUG: unable to handle kernel NULL pointer dereference at 0000000000000010\n[  12.345679] CPU: 0 PID: 1234 Comm: crash Not tainted 5.15.0-...\n[  12.345680] Call Trace:\n[  12.345681]  dump_stack+0x5e/0x70\n[  12.345682]  panic+0x11b/0x2b0\n",
            "ps": "PID  TASK  CPU  COMM  STATE\n1     ffff88800000  0  systemd  S\n1234  ffff8880abc0  0  crash   R",
            "regs": "CPU: 0 PID: 1234 Comm: crash Not tainted 5.15.0-...\nRIP: 00007f1234567890 (panic+0x11b/0x2b0)\nRAX: ffff88800abc1230 RBX: 0000000000000000 RCX: 00007f12345678a0\nRDX: 0000000000000010 RSI: 0000000000000001 RDI: ffffffff81234567\n",
            "kmem": "kmembase: ffff888000000000\nkmersize: 0x100000000\n",
        }

        return mock_responses.get(cmd_lower, f"Mock response for: {command}")

    def get_backtrace(self) -> str:
        """获取内核调用栈。"""
        return self.execute("bt")

    def get_log(self, lines: int = 200) -> str:
        """获取内核日志。

        Args:
            lines: 返回最近多少行日志
        """
        return self.execute(f"log | tail -{lines}")

    def get_processes(self) -> str:
        """查看所有进程状态。"""
        return self.execute("ps")

    def get_registers(self) -> str:
        """查看所有寄存器状态。"""
        return self.execute("regs")

    def get_struct(self, address: str) -> str:
        """解析指定地址的结构体。

        Args:
            address: 结构体地址，如 "0xffff88800abc1230"
        """
        return self.execute(f"struct {address}")

    def disassemble(self, start: str, end: Optional[str] = None) -> str:
        """反汇编代码段。

        Args:
            start: 起始地址
            end: 结束地址（可选）
        """
        if end:
            return self.execute(f"dis {start} {end}")
        return self.execute(f"dis {start}")

    def get_kernel_info(self) -> str:
        """获取内核基本信息。"""
        return self.execute("kmem")

    def search(self, pattern: str, size: int = 8) -> str:
        """在内存中搜索特定模式。

        Args:
            pattern: 搜索模式
            size: 匹配大小
        """
        return self.execute(f"search {pattern} {size}")

    def parse_backtrace(self, bt_output: str) -> BacktraceInfo:
        """解析调用栈输出，提取关键信息。

        Args:
            bt_output: bt 命令的输出

        Returns:
            解析后的 BacktraceInfo
        """
        frames: List[str] = []
        panic_function = ""
        panic_type = ""
        cpu_id = -1

        # 提取 CPU ID
        cpu_match = re.search(r'CPU:\s*(\d+)', bt_output)
        if cpu_match:
            cpu_id = int(cpu_match.group(1))

        # 识别崩溃类型
        if 'BUG:' in bt_output or 'BUG!' in bt_output:
            panic_type = "BUG"
        elif 'Oops:' in bt_output:
            panic_type = "Oops"
        elif 'panic' in bt_output.lower():
            panic_type = "Panic"
        else:
            panic_type = "Unknown"

        # 解析调用帧
        for line in bt_output.split('\n'):
            line = line.strip()
            # 匹配函数调用行，如: panic+0x11b/0x2b0
            frame_match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*(?:\+0x[0-9a-fA-F]+/0x[0-9a-fA-F]+)?)', line)
            if frame_match:
                frame = frame_match.group(1)
                frames.append(frame)
                # 第一个非 dump_stack 的函数通常是崩溃点
                if not panic_function and not frame.startswith('dump_stack'):
                    panic_function = frame

        return BacktraceInfo(
            raw_output=bt_output,
            frames=frames,
            panic_type=panic_type,
            panic_function=panic_function,
            cpu_id=cpu_id,
        )

    def get_parsed_backtrace(self) -> BacktraceInfo:
        """获取并解析调用栈。"""
        bt_output = self.get_backtrace()
        return self.parse_backtrace(bt_output)

    def get_panic_summary(self) -> Dict[str, str]:
        """获取崩溃概要信息。"""
        bt_info = self.get_parsed_backtrace()
        return {
            "panic_type": bt_info.panic_type,
            "panic_function": bt_info.panic_function,
            "cpu_id": str(bt_info.cpu_id),
            "frame_count": str(len(bt_info.frames)),
            "first_frame": bt_info.frames[0] if bt_info.frames else "",
            "raw_bt": bt_info.raw_output[:500],
        }
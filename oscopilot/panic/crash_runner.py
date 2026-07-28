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

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional


class CrashRunnerError(Exception):
    """crash 执行错误。"""


class CrashRunner:
    """crash 工具执行器。

    负责启动 crash 会话、执行命令、解析输出。
    """

    def __init__(self, vmcore_path: str, vmlinux_path: str) -> None:
        self._vmcore_path = Path(vmcore_path)
        self._vmlinux_path = Path(vmlinux_path)

    @property
    def is_available(self) -> bool:
        """检查 crash 工具是否可用。"""
        return shutil.which("crash") is not None

    @property
    def vmcore_exists(self) -> bool:
        """检查 vmcore 文件是否存在。"""
        return self._vmcore_path.is_file()

    @property
    def vmlinux_exists(self) -> bool:
        """检查 vmlinux 文件是否存在。"""
        return self._vmlinux_path.is_file()

    def validate(self) -> List[str]:
        """验证环境，返回错误信息列表。"""
        errors = []

        if not self.is_available:
            errors.append("crash 工具未安装或不在 PATH 中")

        if not self.vmcore_exists:
            errors.append(f"vmcore 文件不存在: {self._vmcore_path}")

        if not self.vmlinux_exists:
            errors.append(f"vmlinux 文件不存在: {self._vmlinux_path}")

        return errors

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
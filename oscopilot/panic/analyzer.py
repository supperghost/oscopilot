"""核心 Panic 分析器。

协调 CrashRunner 和 LLMClient，实现多轮自动化分析。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..auditing import AuditEvent, now_iso
from ..context import AppContext
from ..utils import generate_action_id
from .crash_runner import CrashRunner, CrashRunnerError
from .llm_client import LLMClient, LLMClientError
from .prompts import (
    FINAL_REPORT_PROMPT,
    INITIAL_ANALYSIS_PROMPT,
    ROUND_ANALYSIS_PROMPT,
    SYSTEM_PROMPT,
)


@dataclass
class AnalysisStep:
    """单步分析记录。"""

    round: int
    command: str
    output: str
    llm_analysis: str
    timestamp: str = field(default_factory=now_iso)


@dataclass
class AnalysisResult:
    """分析结果。"""

    success: bool
    root_cause: str = ""
    summary: str = ""
    steps: List[AnalysisStep] = field(default_factory=list)
    report: str = ""
    error: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "success": self.success,
            "root_cause": self.root_cause,
            "summary": self.summary,
            "steps": [
                {
                    "round": s.round,
                    "command": s.command,
                    "output_preview": s.output[:500] + "..." if len(s.output) > 500 else s.output,
                    "llm_analysis": s.llm_analysis,
                    "timestamp": s.timestamp,
                }
                for s in self.steps
            ],
            "report": self.report,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }


class PanicAnalyzer:
    """内核 Panic 自动分析器。

    使用 crash 工具获取崩溃现场数据，借助 LLM 多轮分析定位根因。
    支持 Mock 模式用于测试。
    """

    def __init__(self, ctx: AppContext, mock_mode: bool = False) -> None:
        self._ctx = ctx
        self._mock_mode = mock_mode or ctx.config.panic.enable_mock_mode
        self._crash_runner: Optional[CrashRunner] = None
        self._llm_client: Optional[LLMClient] = None
        self._known_info: List[str] = []
        self._analysis_steps: List[AnalysisStep] = []

    def analyze(
        self,
        vmcore_path: str,
        vmlinux_path: str,
        max_rounds: int = 10,
    ) -> Dict[str, Any]:
        """执行内核 panic 分析。

        Args:
            vmcore_path: vmcore 文件路径
            vmlinux_path: vmlinux 符号文件路径
            max_rounds: 最大分析轮数

        Returns:
            分析结果字典
        """
        start_time = time.time()
        action_id = generate_action_id()

        result = AnalysisResult(success=False)

        try:
            # 初始化 crash runner（支持 Mock 模式）
            self._crash_runner = CrashRunner(
                vmcore_path,
                vmlinux_path,
                mock_mode=self._mock_mode,
            )
            errors = self._crash_runner.validate()
            if errors:
                result.error = "; ".join(errors)
                self._log_audit(action_id, "validation_error", result.error)
                return result.to_dict()

            # 初始化 LLM 客户端（使用 panic 配置的超时）
            self._llm_client = LLMClient(
                base_url=self._ctx.config.llm.base_url,
                api_key=self._ctx.config.llm.api_key,
                model=self._ctx.config.llm.model,
                timeout=self._ctx.config.panic.llm_timeout,
            )
            self._llm_client.add_system_prompt(SYSTEM_PROMPT)

            # 多轮分析
            root_cause_found = False
            for round_num in range(1, max_rounds + 1):
                print(f"\n[轮次 {round_num}/{max_rounds}] 正在分析...")

                try:
                    # 获取 crash 命令
                    prompt = self._build_round_prompt(round_num, max_rounds)
                    llm_response = self._llm_client.chat(prompt)

                    # 检查是否找到根因
                    if "ROOT_CAUSE_FOUND" in llm_response:
                        root_cause_found = True
                        result.root_cause = llm_response
                        break

                    # 执行 crash 命令（使用配置的超时）
                    commands = self._extract_commands(llm_response)
                    crash_timeout = self._ctx.config.panic.crash_timeout
                    for cmd in commands:
                        print(f"  执行: {cmd}")
                        try:
                            output = self._crash_runner.execute(cmd, timeout=crash_timeout)
                            step = AnalysisStep(
                                round=round_num,
                                command=cmd,
                                output=output,
                                llm_analysis=llm_response,
                            )
                            self._analysis_steps.append(step)
                            result.steps.append(step)
                            self._known_info.append(f"[{round_num}] {cmd} 输出: {output[:300]}...")

                            # 将结果反馈给 LLM
                            feedback_prompt = (
                                f"命令 '{cmd}' 的执行结果:\n\n"
                                f"```\n{output}\n```\n\n"
                                f"请分析这个结果，判断是否需要进一步诊断。"
                            )
                            self._llm_client.add_user_message(feedback_prompt)

                        except CrashRunnerError as e:
                            error_msg = f"命令执行失败: {cmd} - {e}"
                            print(f"  警告: {error_msg}")
                            self._known_info.append(error_msg)

                except LLMClientError as e:
                    error_msg = f"LLM 调用失败: {e}"
                    print(f"  错误: {error_msg}")
                    result.steps.append(
                        AnalysisStep(
                            round=round_num,
                            command="llm_call",
                            output="",
                            llm_analysis=error_msg,
                        )
                    )

            # 生成最终报告
            print("\n[生成报告] 正在生成分析报告...")
            result.report = self._generate_final_report(result)
            result.summary = self._extract_summary(result.report)
            result.success = root_cause_found or len(result.steps) > 0

            # 记录审计日志
            self._log_audit(action_id, "analysis_complete", result.summary)

        except Exception as e:
            result.error = f"分析异常: {e}"
            self._log_audit(action_id, "analysis_error", result.error)

        result.duration_seconds = time.time() - start_time
        return result.to_dict()

    def _build_round_prompt(self, round_num: int, max_rounds: int) -> str:
        """构建当前轮次的提示词。"""
        if round_num == 1:
            return INITIAL_ANALYSIS_PROMPT

        # 后续轮次：汇总已知信息
        known_info_text = "\n".join(self._known_info[-10:])  # 最近 10 条
        recent_outputs = []
        for step in self._analysis_steps[-3:]:  # 最近 3 步
            recent_outputs.append(f"命令: {step.command}\n输出: {step.output[:200]}")

        return ROUND_ANALYSIS_PROMPT.format(
            round=round_num,
            max_rounds=max_rounds,
            known_info=known_info_text,
            crash_output="\n\n".join(recent_outputs) if recent_outputs else "暂无历史输出",
        )

    def _extract_commands(self, text: str) -> List[str]:
        """从 LLM 回复中提取 crash 命令。

        支持多种格式：
        - 单行命令: bt
        - 带参数: struct 0xffff88800abc
        - 代码块: ```bt```
        - 中文标签: 【下一步命令】bt
        """
        commands = []

        # 格式1: 代码块内
        code_blocks = re.findall(r'```(?:bash|shell|crash)?\n?(.*?)```', text, re.DOTALL)
        for block in code_blocks:
            for line in block.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    commands.append(line)

        # 格式2: 【下一步命令】后面
        next_cmd_match = re.search(r'【下一步命令】[:：]\s*\n*(.*?)(?=【|$)', text, re.DOTALL)
        if next_cmd_match:
            cmd_text = next_cmd_match.group(1).strip()
            for line in cmd_text.split('\n'):
                line = line.strip()
                if line and 'ROOT_CAUSE_FOUND' not in line:
                    commands.append(line)

        # 格式3: 直接提取像 crash 命令的行
        if not commands:
            for line in text.split('\n'):
                line = line.strip()
                # 匹配已知的 crash 命令模式
                if re.match(r'^(bt|log|ps|regs|struct|dis|kmem|search)\b', line):
                    commands.append(line)
                elif 'ROOT_CAUSE_FOUND' in line:
                    commands.append(line)

        return commands

    def _generate_final_report(self, result: AnalysisResult) -> str:
        """生成最终分析报告。"""
        if not self._llm_client or not result.steps:
            return "分析数据不足，无法生成完整报告。"

        try:
            # 汇总所有分析步骤
            summary_text = "分析过程汇总:\n"
            for step in result.steps:
                summary_text += f"\n--- 轮次 {step.round} ---\n"
                summary_text += f"命令: {step.command}\n"
                summary_text += f"输出: {step.output[:300]}...\n"

            # 请求 LLM 生成报告
            prompt = FINAL_REPORT_PROMPT + "\n\n" + summary_text
            report = self._llm_client.chat(prompt)

            return report

        except LLMClientError as e:
            return f"报告生成失败: {e}\n\n以下是分析步骤摘要:\n" + self._build_steps_summary(result)

    def _extract_summary(self, report: str) -> str:
        """从报告中提取简要摘要。"""
        if "根因" in report:
            lines = report.split('\n')
            for i, line in enumerate(lines):
                if '根因' in line and len(line) > 20:
                    summary_lines = [line]
                    if i + 1 < len(lines) and lines[i + 1].strip():
                        summary_lines.append(lines[i + 1])
                    return ' '.join(summary_lines)

        return report[:200] + "..."

    def _build_steps_summary(self, result: AnalysisResult) -> str:
        """构建步骤摘要。"""
        lines = []
        for step in result.steps:
            lines.append(f"Round {step.round}: {step.command} -> {step.output[:100]}")
        return "\n".join(lines)

    def _log_audit(
        self,
        action_id: str,
        summary: str,
        detail: str,
    ) -> None:
        """记录审计日志。"""
        try:
            self._ctx.auditor.log_event(
                AuditEvent(
                    timestamp=now_iso(),
                    actor=self._ctx.actor,
                    session_id=self._ctx.session_id,
                    action_id=action_id,
                    tool="panic_analyze",
                    args={
                        "summary": summary,
                        "detail": detail[:200],
                    },
                    result_summary=summary,
                    stdout=detail[:500],
                    stderr="",
                    file_diff_hash=None,
                    policy_decision="allow",
                    approval_result="n/a",
                )
            )
        except Exception:
            pass  # 审计失败不影响主流程
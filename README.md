# Linux OS Copilot Agent (MVP)

本项目提供一个可安装的 Python 包与 CLI：`oscopilot`，用于在 Linux 系统上安全运行 OS Copilot Agent 的最小可用版本（MVP）。

> 目标场景：常见问题排查（CPU/内存/磁盘/网络/进程/服务 systemd/日志）、工具与软件部署（apt/yum/dnf）、健康巡检与报告生成，默认支持 Ubuntu/Debian 与 RHEL/CentOS 系。

## 工程结构

```text
os-copilot-agent/
  pyproject.toml          # Python 包配置，提供 oscopilot CLI
  oscopilot/
    __init__.py
    utils.py              # 输入净化（零宽字符防御）、ID 生成
    config.py             # YAML 配置加载与数据类
    auditing.py           # JSON Lines 审计日志 + 简易 metrics
    policy.py             # 策略引擎（白/黑名单、参数约束、速率限制）
    approval.py           # 人机审批（交互 / 队列 + dry-run）
    context.py            # AppContext 聚合配置、策略、审计、审批
    tools/
      __init__.py
      system_info.py      # 安全的 CPU 负载 & 前 5 进程查询
      files.py            # 文件查看 & 带 Diff 的安全追加写入
      systemd_tools.py    # systemd status/start/stop/restart（审批+策略）
      package_manager.py  # apt/yum/dnf 查询与安装（审批+策略）
      mcp_client.py       # JSON-RPC over stdio MCP 客户端
    agent_langchain.py    # LangChain Agent，把工具注册给 LLM
    cli.py                # Typer CLI，实现 oscopilot … 子命令
  examples/
    config.example.yaml   # 配置模板
    audit_example.jsonl   # 示例审计日志片段
  oscopilot.service       # systemd unit 示例（用户服务推荐）
  README.md
```

## 安装与运行

### 环境要求

- Python 3.10+
- Linux（推荐 Ubuntu/Debian 或 RHEL/CentOS 系）
- 能访问 OpenAI 兼容 LLM 接口（或本地代理）

### 安装

```bash
cd os-copilot-agent
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
    """

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx
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
            # 初始化 crash runner
            self._crash_runner = CrashRunner(vmcore_path, vmlinux_path)
            errors = self._crash_runner.validate()
            if errors:
                result.error = "; ".join(errors)
                self._log_audit(action_id, "validation_error", result.error)
                return result.to_dict()

            # 初始化 LLM 客户端
            self._llm_client = LLMClient(
                base_url=self._ctx.config.llm.base_url,
                api_key=self._ctx.config.llm.api_key,
                model=self._ctx.config.llm.model,
                timeout=self._ctx.config.llm.timeout,
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

                    # 执行 crash 命令
                    commands = self._extract_commands(llm_response)
                    for cmd in commands:
                        print(f"  执行: {cmd}")
                        try:
                            output = self._crash_runner.execute(cmd)
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
# 或开发模式
pip install -e .
```

安装完成后将获得 `oscopilot` CLI：

```bash
oscopilot --help
```

### 配置

1. 复制示例配置：

```bash
sudo mkdir -p /etc/oscopilot
sudo cp examples/config.example.yaml /etc/oscopilot/config.yaml
sudo chmod 600 /etc/oscopilot/config.yaml
```

2. 根据实际情况修改 `/etc/oscopilot/config.yaml`：

- `llm`: 配置 LLM base_url/token/model（OpenAI 兼容接口）
- `policy.whitelist_commands`: 允许的 systemd / 包管理命令别名
- `policy.blacklist_patterns`: 高危模式（如 `rm -rf /`）
- `approval`: 审批模式（默认 `interactive`）与 dry-run 开关
- `mcp.servers.sysom_mcp`: 配置 SysOM MCP 的启动命令和工作目录
- `tools.allowed_write_tools`: 允许的变更工具（默认只包含 `append_hosts_mapping`）

日志与审计默认路径：

```yaml
audit:
  log_path: "./logs/oscopilot.log"
  audit_path: "./logs/audit.jsonl"
  metrics_path: "./logs/metrics.json"
```

可根据需要指向 `/var/log/oscopilot/…`。

### systemd 服务示例

`oscopilot.service` 为用户服务示例（推荐）：

```ini
[Unit]
Description=Oscopilot Linux OS Copilot Agent
After=network.target

[Service]
Type=simple
# 建议以用户服务运行，将本 unit 放在 ~/.config/systemd/user/oscopilot.service
ExecStart=/usr/bin/env oscopilot agent run --config /etc/oscopilot/config.yaml
WorkingDirectory=/etc/oscopilot
Restart=on-failure

[Install]
WantedBy=default.target
```

使用步骤（以用户服务为例）：

```bash
mkdir -p ~/.config/systemd/user
cp oscopilot.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now oscopilot.service
```

## CLI 子命令

### 1. Agent：`oscopilot agent run`

启动 LangChain Agent，读取配置，注册安全工具并绑定 LLM：

```bash
# 交互模式
oscopilot agent run --config /etc/oscopilot/config.yaml

# 一次性指令
oscopilot agent run --config /etc/oscopilot/config.yaml \
  --once "检查 CPU 负载并列出前 5 个高 CPU 进程"
```

Agent 内注册的关键工具：

- `check_cpu_and_top_processes`：使用 `psutil` 查询 CPU load + 前 5 进程
- `append_hosts_mapping`：封装 `/etc/hosts` 追加行为
  - 调用前由策略引擎检查
  - 调用时由审批模块展示 Diff + 中文提示并请求确认
  - 审计日志记录 `file_diff_hash`（diff 的 SHA256）

### 2. MCP：`oscopilot mcp exec <tool> <json>`

通过 MCP 客户端（JSON-RPC over stdio）调用如 SysOM MCP 的诊断工具：

```bash
oscopilot mcp exec sysom_mcp sysom.load_diagnose "{\"target\":\"system\"}"
```

行为：

- 从配置 `mcp.servers.sysom_mcp` 读取 `command/args/env/cwd`
- 通过 `--stdio` 启动 MCP 服务器
- 写入 JSON-RPC 请求并读取响应
- 返回结构化结果（以 JSON 打印）
- 记录审计事件 `tool="mcp:<tool>"`，stdout 保存结果 JSON

### 3. 审批队列：`oscopilot approve queue`

当 `approval.mode: queue` 时，高风险操作不会立即执行，而是进入队列文件（例如 `./logs/approval_queue.jsonl`），等待集中审批：

```bash
oscopilot approve queue --config /etc/oscopilot/config.yaml
# 或限制本次审批条数
oscopilot approve queue --config /etc/oscopilot/config.yaml --limit 5
```

行为：

- 逐条读取 `pending` 记录
- 展示操作类型、参数以及（如有）Diff 预览
- 中文提示语：`即将执行如下高风险操作，请仔细检查 Diff 并确认：`
- 对 `file_write` 类型操作，审批通过后真正写盘
- 每条记录在审计日志中写入对应 `approval_result`

### 4. 策略测试：`oscopilot policy test <json>`

快速验证策略引擎对某个操作的判定：

```bash
oscopilot policy test '{"type":"shell","name":"systemctl_start","args":{"unit":"nginx.service"}}'
```

返回示例：

```json
{
  "allowed": true,
  "requires_approval": true,
  "reason": "允许"
}
```

### 5. 审计报告：`oscopilot report last`

查看最近一次 session 的审计摘要：

```bash
oscopilot report last --config /etc/oscopilot/config.yaml
```

输出示例：

```json
{
  "session_id": "...",
  "event_count": 3,
  "tools": {
    "psutil_cpu": 1,
    "append_line": 2
  },
  "last_event": { "...": "..." }
}
```

### 6. Demo：编辑 /etc/hosts（带 Diff + 审批）

为保证可重复自测，提供一个直接的演示命令：

```bash
sudo oscopilot demo-hosts 127.0.0.1 example.local \
  --config /etc/oscopilot/config.yaml
```

流程：

1. 读取 `/etc/hosts` 当前内容
2. 计算追加行后的新内容
3. 生成统一 Diff：`files.append_line_with_approval` 中通过 `difflib.unified_diff` 实现
4. 计算 `file_diff_hash = sha256(diff)`
5. 调用审批模块：展示 Diff 与中文提示，要求键入 `y/yes` 才执行
6. 审批通过时写盘，并将 `file_diff_hash` 写入审计日志

当 `approval.mode = queue` 时，该操作不会立即写盘，而是进入队列，需通过 `oscopilot approve queue` 统一审批。

## 安全与策略落地要点

1. **严禁 auto-approve/YOLO 模式**
   - 不提供任何自动批准开关
   - 高风险操作（文件写入、systemd 启停、包安装）一律走策略 + 审批

2. **文件写入必须 Diff 预览 + 审批 + 审计**
   - `files.append_line_with_approval`：生成统一 Diff、计算哈希
   - 审批提示中展示 Diff
   - 审计日志字段 `file_diff_hash` 写入 Diff 哈希

3. **输入净化与参数校验**
   - `utils.ensure_no_invisible` 检查零宽等不可见字符（防止隐形提示词注入）
   - CLI 中对 `tool`、`params_json`、`operation_json` 等用户输入统一做净化
   - `policy.parameter_regex` 对关键参数（如包名）做正则约束

4. **最小权限与变更工具显式开启**
   - 默认不使用 `sudo`（`tools.use_sudo: false`），避免直接以 root 运行
   - 推荐将 `oscopilot` 部署为用户级 systemd 服务
   - 仅查询类工具默认可用；变更类工具需要在 `tools.allowed_write_tools` 中显式列出

5. **策略引擎**
   - 白名单：只允许配置中声明的命令别名（如 `systemctl_start`、`pkg_install`）
   - 黑名单：拒绝高危模式（如 `rm -rf /`、fork bomb 等）
   - 参数正则：限制包名、服务名、主机名等
   - 速率限制：`max_operations_per_minute` 控制工具调用频率

6. **可观测性**
   - 日志：`auditing.AuditLogger` 将运行日志写入 `log_path`
   - 审计：所有工具调用与审批结果写入 `audit_path`（JSON Lines）
   - 度量：计数器写入 `metrics_path`（JSON），按工具名统计调用次数
   - 追踪：`session_id` 与 `action_id` 贯穿审计记录

## 验收示例（自测建议）

### 示例一：CPU 负载与前 5 个高 CPU 进程

1. 启动 Agent：

```bash
oscopilot agent run --config /etc/oscopilot/config.yaml
```

2. 在对话中输入：

> "请帮我检查当前 CPU 负载，并列出前 5 个高 CPU 进程，顺便解释一下结果。"

3. 期望行为：
   - Agent 调用 `check_cpu_and_top_processes` 工具
   - 输出 CPU load(1/5/15) 与前 5 进程的 PID/CPU/用户名/名称
   - Agent 用中文解释负载与进程含义
   - 审计日志中有一条对应的 `psutil_cpu` 事件

### 示例二：编辑 /etc/hosts 追加一条映射

> 注意：需要确保当前用户具有写入 `/etc/hosts` 的权限，通常需通过 `sudo`。

```bash
sudo oscopilot demo-hosts 127.0.0.1 example.local \
  --config /etc/oscopilot/config.yaml
```

期望行为：

1. 终端展示 `/etc/hosts` 的 Diff 预览（新增行 `127.0.0.1 example.local`）
2. 终端提示中文审批文案：`即将执行如下高风险操作，请仔细检查 Diff 并确认：...`
3. 用户输入 `y` 才继续；否则操作被拒绝并记入审计
4. 审批通过：
   - `/etc/hosts` 落盘
   - 审计日志中有一条 `append_line` 记录，字段 `file_diff_hash` 为 Diff 的 SHA256

### 示例三：通过 SysOM MCP 执行诊断

假设已按文档部署 `sysom_mcp` 并在配置中配置 `mcp.servers.sysom_mcp`：

```bash
oscopilot mcp exec sysom_mcp sysom.load_diagnose "{\"target\":\"system\"}"
```

期望行为：

- CLI 启动 `uv run python sysom_main_mcp.py --stdio`
- 通过 JSON-RPC 发送请求并读取响应
- 打印结构化诊断结果（例如内存/负载/IO 分析）
- 审计日志中记录 `tool="mcp:sysom.load_diagnose"` 的事件

## 多机扩展（占位）

当前 MVP 聚焦单机；多主机场景可通过后续扩展：

- 在配置中增加 SSH 目标定义
- 使用 Paramiko / OpenSSH 执行远程命令，并在本地统一审计
- 或在每台机器上部署本 Agent，通过集中式 LLM 与审批服务进行编排

## 容器化与隔离（占位说明）

为进一步提升安全性，可在后续版本中引入：

- 将变更类操作封装在容器中执行（例如使用 rootless Podman）
- 通过挂载只读/只写路径控制最小文件访问范围
- 利用 seccomp/cgroup 限制子进程能力

> 本 MVP 以最小可用实现为目标，重点落地配置化策略、审批与审计闭环，为后续容器化隔离留出明确的扩展点。

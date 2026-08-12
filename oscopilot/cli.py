"""oscopilot CLI 主入口。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .auditing import AuditEvent, now_iso
from .config import AppConfig, ConfigError, load_config
from .context import AppContext, build_app_context
from .policy import Operation
from .tools import mcp_client, system_info, files, hidden_procs
from .utils import ensure_no_invisible

app = typer.Typer(help="Linux OS Copilot Agent CLI")

agent_app = typer.Typer(help="启动 LangChain Agent")
app.add_typer(agent_app, name="agent")

mcp_app = typer.Typer(help="通过 MCP 执行诊断工具")
app.add_typer(mcp_app, name="mcp")

approve_app = typer.Typer(help="审批队列处理")
app.add_typer(approve_app, name="approve")

policy_app = typer.Typer(help="策略引擎测试")
app.add_typer(policy_app, name="policy")

report_app = typer.Typer(help="审计报告查看")
app.add_typer(report_app, name="report")

panic_app = typer.Typer(help="内核 Panic 分析工具")
app.add_typer(panic_app, name="panic")

detect_app = typer.Typer(help="可疑进程/隐藏进程检测")
app.add_typer(detect_app, name="detect")


def _load_app_context(config_path: Optional[str], actor: str = "oscopilot") -> AppContext:
    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        typer.echo(f"加载配置失败: {exc}")
        raise typer.Exit(code=1)
    return build_app_context(cfg, actor=actor)


@agent_app.command("run")
def agent_run(
    config: Optional[str] = typer.Option(None, "--config", help="配置文件路径 (YAML)"),
    once: Optional[str] = typer.Option(None, "--once", help="一次性指令，不进入交互"),
):
    """启动基于 LangChain 的 Agent。"""

    from .agent_langchain import run_agent

    ctx = _load_app_context(config)
    run_agent(ctx, one_shot_prompt=once)


@mcp_app.command("exec")
def mcp_exec(
    server: str = typer.Argument("sysom_mcp", help="MCP 服务器名称（配置文件 mcp.servers 下的 key）"),
    tool: str = typer.Argument(..., help="要调用的 MCP 工具/方法名"),
    params_json: str = typer.Argument("{}", help="JSON 格式参数"),
    config: Optional[str] = typer.Option(None, "--config", help="配置文件路径"),
):
    """通过 MCP 执行指定诊断工具，并返回结构化结果。"""

    ensure_no_invisible(tool, field="tool")
    ensure_no_invisible(params_json, field="params_json")
    try:
        params = json.loads(params_json or "{}")
    except json.JSONDecodeError as exc:
        typer.echo(f"参数 JSON 解析失败: {exc}")
        raise typer.Exit(code=1)

    ctx = _load_app_context(config)
    client = mcp_client.get_mcp_client(ctx.config.mcp, server)

    from .utils import generate_action_id

    action_id = generate_action_id()
    result = client.exec_tool(tool, params)

    ctx.auditor.log_event(
        AuditEvent(
            timestamp=now_iso(),
            actor=ctx.actor,
            session_id=ctx.session_id,
            action_id=action_id,
            tool=f"mcp:{tool}",
            args={"server": server, "params": params},
            result_summary="MCP 调用完成",
            stdout=json.dumps(result, ensure_ascii=False),
            stderr="",
            file_diff_hash=None,
            policy_decision="allow",
            approval_result="n/a",
        )
    )

    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@approve_app.command("queue")
def approve_queue(
    config: Optional[str] = typer.Option(None, "--config", help="配置文件路径"),
    limit: int = typer.Option(0, "--limit", help="本次最多处理多少条记录，为 0 表示不限"),
):
    """逐条处理审批队列。"""

    ctx = _load_app_context(config)
    ctx.approval.process_queue(limit=limit)


@policy_app.command("test")
def policy_test(
    operation_json: str = typer.Argument(..., help="JSON 格式的操作描述，例如 {\"type\":\"shell\",...}"),
    config: Optional[str] = typer.Option(None, "--config", help="配置文件路径"),
):
    """测试策略引擎对某个操作的评估结果。"""

    ensure_no_invisible(operation_json, field="operation_json")
    try:
        op_raw = json.loads(operation_json)
    except json.JSONDecodeError as exc:
        typer.echo(f"operation_json 解析失败: {exc}")
        raise typer.Exit(code=1)

    op = Operation(
        type=str(op_raw.get("type", "unknown")),
        name=str(op_raw.get("name", "")),
        args=dict(op_raw.get("args") or {}),
    )

    ctx = _load_app_context(config)
    decision = ctx.policy.evaluate(op)
    typer.echo(json.dumps({
        "allowed": decision.allowed,
        "requires_approval": decision.requires_approval,
        "reason": decision.reason,
    }, ensure_ascii=False, indent=2))


@report_app.command("last")
def report_last(
    config: Optional[str] = typer.Option(None, "--config", help="配置文件路径"),
):
    """查看最近一次 session 的审计摘要。"""

    ctx = _load_app_context(config)
    summary = ctx.auditor.summarize_last_session()
    if not summary:
        typer.echo("暂无审计记录。")
        return
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@panic_app.command("analyze")
def panic_analyze(
    vmcore: str = typer.Argument(..., help="kdump vmcore 文件路径"),
    vmlinux: str = typer.Argument(..., help="vmlinux 符号文件路径（需与内核版本匹配）"),
    config: Optional[str] = typer.Option(None, "--config", help="配置文件路径 (YAML)"),
    max_rounds: int = typer.Option(None, "--max-rounds", help="最大分析轮数"),
    output: Optional[str] = typer.Option(None, "--output", help="分析报告输出路径（JSON）"),
    mock: bool = typer.Option(False, "--mock", help="使用 Mock 模式，不执行真实 crash 命令"),
):
    """分析内核 Panic：加载 vmcore + vmlinux，借助 LLM 多轮分析定位根因。"""

    ensure_no_invisible(vmcore, field="vmcore")
    ensure_no_invisible(vmlinux, field="vmlinux")

    ctx = _load_app_context(config)

    from .panic.analyzer import PanicAnalyzer

    # 使用配置中的默认值
    if max_rounds is None:
        max_rounds = ctx.config.panic.default_max_rounds

    analyzer = PanicAnalyzer(ctx, mock_mode=mock)
    result = analyzer.analyze(
        vmcore_path=vmcore,
        vmlinux_path=vmlinux,
        max_rounds=max_rounds,
    )

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        typer.echo(f"分析报告已保存至: {output}")
    else:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@panic_app.command("validate")
def panic_validate(
    vmcore: str = typer.Argument(..., help="kdump vmcore 文件路径"),
    vmlinux: str = typer.Argument(..., help="vmlinux 符号文件路径"),
):
    """验证 Panic 分析环境：检查 crash 工具可用性、文件存在性等。"""

    ensure_no_invisible(vmcore, field="vmcore")
    ensure_no_invisible(vmlinux, field="vmlinux")

    from .panic.crash_runner import CrashRunner

    runner = CrashRunner(vmcore, vmlinux)
    env_info = runner.get_env_info()

    typer.echo("=== Panic 分析环境检查 ===\n")
    typer.echo(f"crash 工具: {'✓ 可用' if env_info.crash_available else '✗ 不可用'}")
    if env_info.crash_version:
        typer.echo(f"crash 版本: {env_info.crash_version}")

    typer.echo(f"vmcore 文件: {'✓ 存在' if env_info.vmcore_exists else '✗ 不存在'}")
    if env_info.vmcore_size:
        size_mb = env_info.vmcore_size / (1024 * 1024)
        typer.echo(f"vmcore 大小: {size_mb:.2f} MB")

    typer.echo(f"vmlinux 文件: {'✓ 存在' if env_info.vmlinux_exists else '✗ 不存在'}")
    if env_info.vmlinux_size:
        size_mb = env_info.vmlinux_size / (1024 * 1024)
        typer.echo(f"vmlinux 大小: {size_mb:.2f} MB")

    if env_info.is_ready:
        typer.echo("\n✓ 环境检查通过，可以进行 Panic 分析。")
    else:
        typer.echo("\n✗ 环境检查失败:")
        for error in env_info.errors:
            typer.echo(f"  - {error}")
        raise typer.Exit(code=1)


@panic_app.command("mock-analyze")
def panic_mock_analyze(
    config: Optional[str] = typer.Option(None, "--config", help="配置文件路径 (YAML)"),
    max_rounds: int = typer.Option(5, "--max-rounds", help="最大分析轮数"),
    output: Optional[str] = typer.Option(None, "--output", help="分析报告输出路径（JSON）"),
):
    """使用 Mock 数据模拟 Panic 分析，用于测试和演示。"""

    ctx = _load_app_context(config)

    from .panic.analyzer import PanicAnalyzer

    # 使用 Mock vmcore 和 vmlinux 路径（不需要真实存在）
    mock_vmcore = "/tmp/mock_vmcore"
    mock_vmlinux = "/tmp/mock_vmlinux"

    typer.echo("=== Mock Panic 分析 ===")
    typer.echo("使用模拟数据进行分析测试...\n")

    analyzer = PanicAnalyzer(ctx, mock_mode=True)
    result = analyzer.analyze(
        vmcore_path=mock_vmcore,
        vmlinux_path=mock_vmlinux,
        max_rounds=max_rounds,
    )

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        typer.echo(f"分析报告已保存至: {output}")
    else:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@detect_app.command("hidden-procs")
def detect_hidden_procs(
    config: Optional[str] = typer.Option(None, "--config", help="配置文件路径 (YAML)"),
    summary_only: bool = typer.Option(False, "--summary-only", help="仅输出摘要，不打印完整报告"),
):
    """检测可疑/隐藏进程：按三层架构（进程发现/隐藏检测/行为检测）全面扫描。

    覆盖 9 种检测技术：三源 PID 对比、内核模块隐藏、LD_PRELOAD rootkit、
    PID namespace 异常、ptrace 注入、socket 隐藏、exe 已删除、匿名可执行内存、
    伪装进程名与异常父子关系。"""

    ctx = _load_app_context(config)
    report = hidden_procs.detect_hidden_processes(ctx)

    if summary_only:
        typer.echo(report["summary"])
        return

    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


@app.command("demo-hosts")
def demo_hosts_append(
    ip: str = typer.Argument(..., help="要追加的 IP 地址"),
    hostname: str = typer.Argument(..., help="要追加的主机名"),
    config: Optional[str] = typer.Option(None, "--config", help="配置文件路径"),
):
    """演示：向 /etc/hosts 追加一条映射，展示 Diff -> 审批 -> 审计。"""

    ctx = _load_app_context(config)
    line = f"{ip} {hostname}"
    result = files.append_line_with_approval(ctx, "/etc/hosts", line=line)
    typer.echo(f"结果: {result}")


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()


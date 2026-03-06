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
from .tools import mcp_client, system_info, files
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


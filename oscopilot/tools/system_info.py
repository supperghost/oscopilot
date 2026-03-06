"""系统信息与安全查询工具。

尽量使用 psutil 等库，避免直接裸 shell。"""

from __future__ import annotations

import psutil

from typing import List

from ..auditing import AuditEvent, now_iso
from ..context import AppContext
from ..policy import Operation
from ..utils import generate_action_id


def cpu_load_and_top_processes(ctx: AppContext, limit: int = 5) -> str:
    """返回 CPU 平均负载和前 N 个高 CPU 进程信息。"""

    op = Operation(type="shell", name="psutil_cpu", args={"limit": limit})
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
                policy_decision="denied",
                approval_result="rejected",
                stdout="",
                stderr="",
                file_diff_hash=None,
            )
        )
        raise RuntimeError(f"策略拒绝: {decision.reason}")

    load1, load5, load15 = psutil.getloadavg()
    procs = []
    for p in psutil.process_iter(attrs=["pid", "name", "username", "cpu_percent"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x.get("cpu_percent", 0), reverse=True)
    top = procs[:limit]

    lines: List[str] = []
    lines.append(f"CPU load (1/5/15min): {load1:.2f} {load5:.2f} {load15:.2f}")
    lines.append("Top processes by CPU:")
    for p in top:
        lines.append(
            f"PID={p['pid']} CPU={p['cpu_percent']:.1f}% USER={p.get('username','?')} NAME={p.get('name','?')}"
        )
    summary = "\n".join(lines)

    ctx.auditor.log_event(
        AuditEvent(
            timestamp=now_iso(),
            actor=ctx.actor,
            session_id=ctx.session_id,
            action_id=action_id,
            tool=op.name,
            args=op.args,
            result_summary="CPU 负载与前五进程查询完成",
            stdout=summary,
            stderr="",
            file_diff_hash=None,
            policy_decision="allow",
            approval_result="n/a",
        )
    )
    return summary


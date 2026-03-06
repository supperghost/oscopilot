"""systemd 相关查询与控制工具。"""

from __future__ import annotations

import subprocess
from typing import List

from ..auditing import AuditEvent, now_iso
from ..context import AppContext
from ..policy import Operation
from ..utils import generate_action_id, sanitize_str_list


def systemctl_status(ctx: AppContext, unit: str) -> str:
    cmd = ["systemctl", "status", unit]
    cmd = sanitize_str_list(cmd, field="systemctl_status")
    op = Operation(type="systemd", name="systemctl_status", args={"unit": unit})
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

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    stdout = proc.stdout
    stderr = proc.stderr

    ctx.auditor.log_event(
        AuditEvent(
            timestamp=now_iso(),
            actor=ctx.actor,
            session_id=ctx.session_id,
            action_id=action_id,
            tool=op.name,
            args=op.args,
            result_summary="systemctl status 查询完成",
            stdout=stdout,
            stderr=stderr,
            file_diff_hash=None,
            policy_decision="allow",
            approval_result="n/a",
        )
    )
    return stdout or stderr


def _systemctl_change(ctx: AppContext, unit: str, action: str) -> str:
    cmd = ["systemctl", action, unit]
    cmd = sanitize_str_list(cmd, field="systemctl")
    op = Operation(type="systemd", name=f"systemctl_{action}", args={"unit": unit})
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

    def apply() -> str:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            return f"systemctl {action} {unit} 成功"
        raise RuntimeError(proc.stderr or f"systemctl {action} 失败，退出码 {proc.returncode}")

    approval_result = ctx.approval.request_approval(op, action_id=action_id, diff=None, apply_fn=apply)
    return approval_result


def systemctl_start(ctx: AppContext, unit: str) -> str:
    return _systemctl_change(ctx, unit, "start")


def systemctl_stop(ctx: AppContext, unit: str) -> str:
    return _systemctl_change(ctx, unit, "stop")


def systemctl_restart(ctx: AppContext, unit: str) -> str:
    return _systemctl_change(ctx, unit, "restart")


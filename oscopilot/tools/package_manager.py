"""包管理查询与安装工具（apt/yum/dnf）。"""

from __future__ import annotations

import shutil
import subprocess
from typing import List

from ..auditing import AuditEvent, now_iso
from ..context import AppContext
from ..policy import Operation
from ..utils import generate_action_id, sanitize_str_list


def _detect_pm() -> str:
    for pm in ("apt-get", "dnf", "yum"):
        if shutil.which(pm):
            return pm
    raise RuntimeError("未检测到受支持的包管理器 (apt-get/dnf/yum)")


def search_package(ctx: AppContext, name: str) -> str:
    pm = _detect_pm()
    if pm == "apt-get":
        cmd = ["apt-cache", "search", name]
    else:
        cmd = [pm, "search", name]
    cmd = sanitize_str_list(cmd, field="pkg_search")

    op = Operation(type="package", name="pkg_search", args={"name": name})
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
            result_summary="包搜索完成",
            stdout=stdout,
            stderr=stderr,
            file_diff_hash=None,
            policy_decision="allow",
            approval_result="n/a",
        )
    )
    return stdout or stderr


def install_package(ctx: AppContext, name: str) -> str:
    pm = _detect_pm()
    base_cmd: List[str]
    if pm == "apt-get":
        base_cmd = [pm, "install", "-y", name]
    else:
        base_cmd = [pm, "install", "-y", name]
    if ctx.config.tools.use_sudo:
        cmd = ["sudo", *base_cmd]
    else:
        cmd = base_cmd
    cmd = sanitize_str_list(cmd, field="pkg_install")

    op = Operation(type="package", name="pkg_install", args={"name": name})
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
            return f"已安装包 {name}"
        raise RuntimeError(proc.stderr or f"安装 {name} 失败，退出码 {proc.returncode}")

    approval_result = ctx.approval.request_approval(op, action_id=action_id, diff=None, apply_fn=apply)
    return approval_result


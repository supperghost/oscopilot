"""文件查看与安全编辑工具。"""

from __future__ import annotations

import hashlib
import difflib
from pathlib import Path
from typing import Optional

from ..auditing import AuditEvent, now_iso
from ..context import AppContext
from ..policy import Operation
from ..utils import ensure_no_invisible, generate_action_id


_MAX_VIEW_SIZE = 1024 * 1024  # 1MB


def view_file(ctx: AppContext, path: str) -> str:
    ensure_no_invisible(path, field="path")
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"文件不存在: {path}")
    content = p.read_text(encoding="utf-8", errors="ignore")
    if len(content) > _MAX_VIEW_SIZE:
        content = content[:_MAX_VIEW_SIZE] + "\n... (truncated)"

    op = Operation(type="shell", name="view_file", args={"path": path})
    action_id = generate_action_id()
    ctx.auditor.log_event(
        AuditEvent(
            timestamp=now_iso(),
            actor=ctx.actor,
            session_id=ctx.session_id,
            action_id=action_id,
            tool=op.name,
            args=op.args,
            result_summary="文件查看",
            stdout=content,
            stderr="",
            file_diff_hash=None,
            policy_decision="allow",
            approval_result="n/a",
        )
    )
    return content


def _unified_diff(old: str, new: str, path: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"{path} (before)",
            tofile=f"{path} (after)",
            lineterm="",
        )
    )


def _hash_diff(diff: str) -> str:
    return hashlib.sha256(diff.encode("utf-8")).hexdigest()


def append_line_with_approval(ctx: AppContext, path: str, line: str) -> str:
    """示例：向 /etc/hosts 追加一行，带 Diff 预览 + 审批 + 审计。"""

    ensure_no_invisible(path, field="path")
    ensure_no_invisible(line, field="line")
    p = Path(path)
    if p.exists():
        old = p.read_text(encoding="utf-8", errors="ignore")
    else:
        old = ""
    new = old.rstrip("\n") + "\n" + line + "\n"
    diff = _unified_diff(old, new, path)
    diff_hash = _hash_diff(diff)

    op = Operation(
        type="file_write",
        name="append_line",
        args={"path": path, "line": line, "diff_hash": diff_hash},
    )
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
                file_diff_hash=diff_hash,
                policy_decision="denied",
                approval_result="rejected",
            )
        )
        raise RuntimeError(f"策略拒绝: {decision.reason}")

    # 队列模式时，需要把完整 new_content 放入 args，方便后续 approve queue 落盘
    op.args["new_content"] = new

    def apply() -> str:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(new, encoding="utf-8")
        return f"已写入 {path}，diff_hash={diff_hash}"

    approval_result = ctx.approval.request_approval(op, action_id=action_id, diff=diff, apply_fn=apply)

    ctx.auditor.log_event(
        AuditEvent(
            timestamp=now_iso(),
            actor=ctx.actor,
            session_id=ctx.session_id,
            action_id=action_id,
            tool=op.name,
            args=op.args,
            result_summary="文件追加操作完成",
            stdout="",
            stderr="",
            file_diff_hash=diff_hash,
            policy_decision="allow",
            approval_result=approval_result,
        )
    )
    return approval_result


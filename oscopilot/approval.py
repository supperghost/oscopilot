"""人机协作审批模块。

支持：
- 交互式审批（默认）
- 队列审批（将操作写入队列文件，后续通过 `oscopilot approve queue` 逐条确认）
- dry-run 模式：即使审批通过也不真正执行，只记录审计

严禁 auto-approve 模式，所有高风险操作必须经过人工确认。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .auditing import AuditEvent, AuditLogger, now_iso
from .config import ApprovalConfig
from .policy import Operation


@dataclass
class ApprovalQueueEntry:
    id: str
    enqueued_at: str
    status: str  # pending | approved | rejected | dry_run
    operation: Operation
    diff: Optional[str] = None


class ApprovalManager:
    def __init__(self, cfg: ApprovalConfig, auditor: AuditLogger, actor: str, session_id: str) -> None:
        self.cfg = cfg
        self.auditor = auditor
        self.actor = actor
        self.session_id = session_id
        Path(self.cfg.queue_path).parent.mkdir(parents=True, exist_ok=True)

    # 交互式审批
    def _interactive_confirm(self, message: str) -> bool:
        print("".join(["\n", message, "\n", "是否批准? [y/N]: "]), end="")
        resp = input().strip().lower()
        return resp in {"y", "yes"}

    def _enqueue(self, entry: ApprovalQueueEntry) -> None:
        data = {
            "id": entry.id,
            "enqueued_at": entry.enqueued_at,
            "status": entry.status,
            "operation": {
                "type": entry.operation.type,
                "name": entry.operation.name,
                "args": entry.operation.args,
            },
            "diff": entry.diff,
        }
        with open(self.cfg.queue_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def request_approval(
        self,
        op: Operation,
        action_id: str,
        diff: Optional[str],
        apply_fn: Optional[Callable[[], Any]],
    ) -> str:
        """请求审批并根据配置执行或入队。

        返回审批结果：approved/rejected/dry_run/queued
        """

        if not self.cfg.enabled:
            # 即使关闭，也不允许自动执行高风险操作，因此这里仍然要求确认
            print("当前策略禁止关闭审批，已强制启用人工确认。")

        # 文案
        header = self.cfg.prompt_prefix
        detail_lines = [
            f"操作类型: {op.type}",
            f"操作名称: {op.name}",
            f"参数: {json.dumps(op.args, ensure_ascii=False)}",
        ]
        if diff:
            detail_lines.append("变更 Diff 预览:\n" + diff)
        message = header + "\n" + "\n".join(detail_lines)

        if self.cfg.mode == "queue":
            from .utils import generate_action_id

            entry = ApprovalQueueEntry(
                id=action_id,
                enqueued_at=now_iso(),
                status="pending",
                operation=op,
                diff=diff,
            )
            self._enqueue(entry)
            self.auditor.log_event(
                AuditEvent(
                    timestamp=now_iso(),
                    actor=self.actor,
                    session_id=self.session_id,
                    action_id=action_id,
                    tool=op.name,
                    args=op.args,
                    result_summary="已进入审批队列，待后续人工确认",
                    stdout="",
                    stderr="",
                    file_diff_hash=None,
                    policy_decision="pending",
                    approval_result="queued",
                )
            )
            return "queued"

        # 交互式审批
        approved = self._interactive_confirm(message)
        if not approved:
            self.auditor.log_event(
                AuditEvent(
                    timestamp=now_iso(),
                    actor=self.actor,
                    session_id=self.session_id,
                    action_id=action_id,
                    tool=op.name,
                    args=op.args,
                    result_summary="人工拒绝执行",
                    stdout="",
                    stderr="",
                    file_diff_hash=None,
                    policy_decision="denied",
                    approval_result="rejected",
                )
            )
            return "rejected"

        if self.cfg.dry_run:
            # 记录但不执行
            self.auditor.log_event(
                AuditEvent(
                    timestamp=now_iso(),
                    actor=self.actor,
                    session_id=self.session_id,
                    action_id=action_id,
                    tool=op.name,
                    args=op.args,
                    result_summary="dry-run：已批准但未实际执行",
                    stdout="",
                    stderr="",
                    file_diff_hash=None,
                    policy_decision="allow",
                    approval_result="dry_run",
                )
            )
            return "dry_run"

        # 真正执行
        stdout = ""
        stderr = ""
        try:
            result = apply_fn() if apply_fn else None
            summary = "执行成功" if result is None else str(result)
            approval_result = "approved"
        except Exception as exc:  # noqa: BLE001
            summary = f"执行失败: {exc}"
            stderr = str(exc)
            approval_result = "failed"

        self.auditor.log_event(
            AuditEvent(
                timestamp=now_iso(),
                actor=self.actor,
                session_id=self.session_id,
                action_id=action_id,
                tool=op.name,
                args=op.args,
                result_summary=summary,
                stdout=stdout,
                stderr=stderr,
                file_diff_hash=None,
                policy_decision="allow",
                approval_result=approval_result,
            )
        )
        return approval_result

    # 审批队列处理
    def process_queue(self, limit: int = 0) -> None:
        """逐条处理审批队列中的 pending 记录。

        limit>0 时最多处理指定条数。
        """

        if not os.path.exists(self.cfg.queue_path):
            print("审批队列为空。")
            return

        entries: List[Dict[str, Any]] = []
        with open(self.cfg.queue_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        processed = 0
        new_entries: List[Dict[str, Any]] = []
        for e in entries:
            if e.get("status") != "pending":
                new_entries.append(e)
                continue
            if limit and processed >= limit:
                new_entries.append(e)
                continue

            op_raw = e.get("operation") or {}
            op = Operation(type=op_raw.get("type", "unknown"), name=op_raw.get("name", ""), args=op_raw.get("args") or {})
            diff = e.get("diff")

            header = self.cfg.prompt_prefix + " (队列审批)"
            detail_lines = [
                f"操作 ID: {e.get('id')}",
                f"操作类型: {op.type}",
                f"操作名称: {op.name}",
                f"参数: {json.dumps(op.args, ensure_ascii=False)}",
            ]
            if diff:
                detail_lines.append("变更 Diff 预览:\n" + diff)
            message = header + "\n" + "\n".join(detail_lines)

            approved = self._interactive_confirm(message)
            action_id = str(e.get("id"))
            if not approved:
                e["status"] = "rejected"
                self.auditor.log_event(
                    AuditEvent(
                        timestamp=now_iso(),
                        actor=self.actor,
                        session_id=self.session_id,
                        action_id=action_id,
                        tool=op.name,
                        args=op.args,
                        result_summary="队列审批被拒绝",
                        stdout="",
                        stderr="",
                        file_diff_hash=None,
                        policy_decision="denied",
                        approval_result="rejected",
                    )
                )
                new_entries.append(e)
                processed += 1
                continue

            if self.cfg.dry_run:
                e["status"] = "dry_run"
                self.auditor.log_event(
                    AuditEvent(
                        timestamp=now_iso(),
                        actor=self.actor,
                        session_id=self.session_id,
                        action_id=action_id,
                        tool=op.name,
                        args=op.args,
                        result_summary="队列 dry-run：已批准但未执行",
                        stdout="",
                        stderr="",
                        file_diff_hash=None,
                        policy_decision="allow",
                        approval_result="dry_run",
                    )
                )
                new_entries.append(e)
                processed += 1
                continue

            # 真正执行，仅对 file_write 支持队列（示例场景足够）
            if op.type == "file_write":
                path = op.args.get("path")
                new_content = op.args.get("new_content")
                if isinstance(path, str) and isinstance(new_content, str):
                    try:
                        Path(path).parent.mkdir(parents=True, exist_ok=True)
                        with open(path, "w", encoding="utf-8") as wf:
                            wf.write(new_content)
                        e["status"] = "approved"
                        summary = f"已写入文件 {path}"
                        approval_result = "approved"
                    except Exception as exc:  # noqa: BLE001
                        summary = f"写入失败: {exc}"
                        approval_result = "failed"
                else:
                    summary = "队列记录格式异常，未执行"
                    approval_result = "failed"
            else:
                summary = "当前队列暂不支持此操作类型，仅记录审批结果"
                approval_result = "approved"
                e["status"] = "approved"

            self.auditor.log_event(
                AuditEvent(
                    timestamp=now_iso(),
                    actor=self.actor,
                    session_id=self.session_id,
                    action_id=action_id,
                    tool=op.name,
                    args=op.args,
                    result_summary=summary,
                    stdout="",
                    stderr="",
                    file_diff_hash=None,
                    policy_decision="allow",
                    approval_result=approval_result,
                )
            )

            new_entries.append(e)
            processed += 1

        # 覆盖写回队列文件
        with open(self.cfg.queue_path, "w", encoding="utf-8") as f:
            for e in new_entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

        print(f"本次共处理审批记录 {processed} 条。")


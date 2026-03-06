"""审计与简单度量模块。

- 审计日志：JSON Lines，字段包含 timestamp/actor/session_id/tool/args/result_summary/stdout/stderr/file_diff_hash/policy_decision/approval_result/action_id。
- 度量：简单计数写入 JSON 文件。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .config import AuditConfig


@dataclass
class AuditEvent:
    timestamp: str
    actor: str
    session_id: str
    action_id: str
    tool: str
    args: Dict[str, Any]
    result_summary: str = ""
    stdout: str = ""
    stderr: str = ""
    file_diff_hash: Optional[str] = None
    policy_decision: Optional[str] = None
    approval_result: Optional[str] = None


class AuditLogger:
    def __init__(self, cfg: AuditConfig) -> None:
        self.cfg = cfg
        Path(self.cfg.audit_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.cfg.log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.cfg.metrics_path).parent.mkdir(parents=True, exist_ok=True)
        self._logger = self._init_logger()

    def _init_logger(self) -> logging.Logger:
        logger = logging.getLogger("oscopilot")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            fh = logging.FileHandler(self.cfg.log_path, encoding="utf-8")
            fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        return logger

    def log_event(self, event: AuditEvent) -> None:
        line = json.dumps(asdict(event), ensure_ascii=False)
        with open(self.cfg.audit_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        self._logger.info(
            "tool=%s session=%s action=%s result=%s",
            event.tool,
            event.session_id,
            event.action_id,
            event.result_summary,
        )
        self._increment_metric("tool_calls", event.tool)

    def _load_metrics(self) -> Dict[str, Any]:
        if not os.path.exists(self.cfg.metrics_path):
            return {}
        try:
            with open(self.cfg.metrics_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_metrics(self, data: Dict[str, Any]) -> None:
        with open(self.cfg.metrics_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _increment_metric(self, category: str, key: str, delta: int = 1) -> None:
        data = self._load_metrics()
        cat = data.setdefault(category, {})
        cat[key] = int(cat.get(key, 0)) + delta
        self._save_metrics(data)

    def summarize_last_session(self) -> Optional[Dict[str, Any]]:
        """读取最近一个 session 的审计摘要。

        简化实现：
        - 扫描所有记录，找到最后一个 session_id
        - 统计该 session 的操作数量、工具分布等
        """

        if not os.path.exists(self.cfg.audit_path):
            return None
        last_session: Optional[str] = None
        events: list[Dict[str, Any]] = []
        with open(self.cfg.audit_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                events.append(rec)
                last_session = rec.get("session_id") or last_session
        if not events or not last_session:
            return None
        session_events = [e for e in events if e.get("session_id") == last_session]
        tool_counts: Dict[str, int] = {}
        for e in session_events:
            t = e.get("tool") or "unknown"
            tool_counts[t] = tool_counts.get(t, 0) + 1
        return {
            "session_id": last_session,
            "event_count": len(session_events),
            "tools": tool_counts,
            "last_event": session_events[-1],
        }


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


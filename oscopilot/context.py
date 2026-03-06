"""应用上下文对象，集中承载配置、策略、审计与审批实例。"""

from __future__ import annotations

from dataclasses import dataclass

from .auditing import AuditLogger
from .config import AppConfig
from .policy import PolicyEngine
from .approval import ApprovalManager
from .utils import generate_session_id


@dataclass
class AppContext:
    config: AppConfig
    auditor: AuditLogger
    policy: PolicyEngine
    approval: ApprovalManager
    actor: str
    session_id: str


def build_app_context(config: AppConfig, actor: str = "oscopilot") -> AppContext:
    from .config import AuditConfig  # avoid cycles

    session_id = generate_session_id()
    auditor = AuditLogger(config.audit)
    policy = PolicyEngine(config.policy)
    approval = ApprovalManager(config.approval, auditor, actor=actor, session_id=session_id)
    return AppContext(
        config=config,
        auditor=auditor,
        policy=policy,
        approval=approval,
        actor=actor,
        session_id=session_id,
    )


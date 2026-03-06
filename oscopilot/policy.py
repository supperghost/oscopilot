"""简单策略引擎。

功能：
- 白名单/黑名单命令检查
- 参数正则约束（按键名匹配）
- 每分钟最大操作次数限流（进程内）
"""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

from .config import PolicyConfig


@dataclass
class Operation:
    type: str  # shell | file_write | mcp_tool | systemd | package
    name: str
    args: Dict[str, Any]


@dataclass
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str = ""


class PolicyEngine:
    def __init__(self, cfg: PolicyConfig) -> None:
        self.cfg = cfg
        self._timestamps: Deque[float] = deque()
        self._compiled_blacklist = [re.compile(p) for p in cfg.blacklist_patterns]
        self._compiled_param = {k: re.compile(v) for k, v in cfg.parameter_regex.items()}

    def _check_rate_limit(self) -> Optional[str]:
        if self.cfg.max_operations_per_minute <= 0:
            return None
        now = time.time()
        window = 60.0
        self._timestamps.append(now)
        while self._timestamps and now - self._timestamps[0] > window:
            self._timestamps.popleft()
        if len(self._timestamps) > self.cfg.max_operations_per_minute:
            return "超过策略配置的每分钟最大操作次数限制"
        return None

    def evaluate(self, op: Operation) -> PolicyDecision:
        # 速率限制
        rl = self._check_rate_limit()
        if rl:
            return PolicyDecision(allowed=False, requires_approval=False, reason=rl)

        # 高风险类型默认需要人工审批
        high_risk_types = {"file_write", "systemd", "package"}
        requires_approval = op.type in high_risk_types

        # 白名单
        if op.type in {"shell", "systemd", "package"}:
            if self.cfg.whitelist_commands and op.name not in self.cfg.whitelist_commands:
                return PolicyDecision(
                    allowed=False,
                    requires_approval=False,
                    reason=f"命令 {op.name} 不在白名单内",
                )

        # 黑名单模式
        full_text = op.name + " " + " ".join(str(v) for v in op.args.values())
        for pat in self._compiled_blacklist:
            if pat.search(full_text):
                return PolicyDecision(
                    allowed=False,
                    requires_approval=False,
                    reason=f"命令/参数命中黑名单模式: {pat.pattern}",
                )

        # 参数范围约束（简化：按 key 匹配）
        for key, regex in self._compiled_param.items():
            if key in op.args:
                if not regex.fullmatch(str(op.args[key])):
                    return PolicyDecision(
                        allowed=False,
                        requires_approval=False,
                        reason=f"参数 {key} 不符合策略约束 {regex.pattern}",
                    )

        return PolicyDecision(allowed=True, requires_approval=requires_approval, reason="允许")


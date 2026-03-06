"""配置加载与数据结构。

配置文件使用 YAML，示例见 examples/config.example.yaml。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 30


@dataclass
class PolicyConfig:
    whitelist_commands: List[str] = field(default_factory=list)
    blacklist_patterns: List[str] = field(default_factory=list)
    parameter_regex: Dict[str, str] = field(default_factory=dict)
    max_operations_per_minute: int = 30


@dataclass
class AuditConfig:
    log_path: str = "./logs/oscopilot.log"
    audit_path: str = "./logs/audit.jsonl"
    metrics_path: str = "./logs/metrics.json"


@dataclass
class ApprovalConfig:
    enabled: bool = True
    dry_run: bool = False
    mode: str = "interactive"  # interactive | queue
    queue_path: str = "./logs/approval_queue.jsonl"
    prompt_prefix: str = "即将执行如下高风险操作，请确认："


@dataclass
class MCPServerConfig:
    command: str = "uv"
    args: List[str] = field(default_factory=lambda: ["run", "python", "sysom_main_mcp.py", "--stdio"])
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    timeout_ms: int = 30000


@dataclass
class MCPConfig:
    servers: Dict[str, MCPServerConfig] = field(default_factory=dict)


@dataclass
class ToolsConfig:
    enable_destructive_tools: bool = False
    allowed_write_tools: List[str] = field(default_factory=list)
    use_sudo: bool = False


@dataclass
class AppConfig:
    llm: LLMConfig
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    approval: ApprovalConfig = field(default_factory=ApprovalConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)


class ConfigError(Exception):
    pass


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_first_existing(paths: List[Path]) -> Optional[Path]:
    for p in paths:
        if p.is_file():
            return p
    return None


def find_default_config_path() -> Optional[Path]:
    candidates: List[Path] = []
    etc_path = Path("/etc/oscopilot/config.yaml")
    candidates.append(etc_path)
    home = os.environ.get("HOME")
    if home:
        candidates.append(Path(home) / ".config/oscopilot/config.yaml")
    return _get_first_existing(candidates)


def load_config(path: Optional[str] = None) -> AppConfig:
    """从指定路径或默认路径加载配置。"""

    cfg_path: Optional[Path]
    if path:
        cfg_path = Path(path)
        if not cfg_path.is_file():
            raise ConfigError(f"指定的配置文件不存在: {cfg_path}")
    else:
        cfg_path = find_default_config_path()
        if cfg_path is None:
            raise ConfigError("未找到配置文件，请在 /etc/oscopilot 或 $HOME/.config/oscopilot 下创建 config.yaml")

    raw = _load_yaml(cfg_path)

    llm_raw = raw.get("llm") or {}
    llm = LLMConfig(
        base_url=str(llm_raw.get("base_url", "https://api.openai.com/v1")),
        api_key=str(llm_raw.get("api_key", "")),
        model=str(llm_raw.get("model", "gpt-4o")),
        timeout=int(llm_raw.get("timeout", 30)),
    )

    policy_raw = raw.get("policy") or {}
    policy = PolicyConfig(
        whitelist_commands=list(policy_raw.get("whitelist_commands", [])),
        blacklist_patterns=list(policy_raw.get("blacklist_patterns", [])),
        parameter_regex=dict(policy_raw.get("parameter_regex", {})),
        max_operations_per_minute=int(policy_raw.get("max_operations_per_minute", 30)),
    )

    audit_raw = raw.get("audit") or {}
    audit = AuditConfig(
        log_path=str(audit_raw.get("log_path", "./logs/oscopilot.log")),
        audit_path=str(audit_raw.get("audit_path", "./logs/audit.jsonl")),
        metrics_path=str(audit_raw.get("metrics_path", "./logs/metrics.json")),
    )

    approval_raw = raw.get("approval") or {}
    approval = ApprovalConfig(
        enabled=bool(approval_raw.get("enabled", True)),
        dry_run=bool(approval_raw.get("dry_run", False)),
        mode=str(approval_raw.get("mode", "interactive")),
        queue_path=str(approval_raw.get("queue_path", "./logs/approval_queue.jsonl")),
        prompt_prefix=str(approval_raw.get("prompt_prefix", "即将执行如下高风险操作，请确认：")),
    )

    mcp_raw = raw.get("mcp") or {}
    servers_cfg: Dict[str, MCPServerConfig] = {}
    servers_raw = mcp_raw.get("servers") or {}
    for name, srv in servers_raw.items():
        servers_cfg[name] = MCPServerConfig(
            command=str(srv.get("command", "uv")),
            args=list(srv.get("args", ["run", "python", "sysom_main_mcp.py", "--stdio"])),
            env={str(k): str(v) for k, v in (srv.get("env") or {}).items()},
            cwd=srv.get("cwd"),
            timeout_ms=int(srv.get("timeout_ms", 30000)),
        )
    mcp = MCPConfig(servers=servers_cfg)

    tools_raw = raw.get("tools") or {}
    tools = ToolsConfig(
        enable_destructive_tools=bool(tools_raw.get("enable_destructive_tools", False)),
        allowed_write_tools=list(tools_raw.get("allowed_write_tools", [])),
        use_sudo=bool(tools_raw.get("use_sudo", False)),
    )

    return AppConfig(
        llm=llm,
        policy=policy,
        audit=audit,
        approval=approval,
        mcp=mcp,
        tools=tools,
    )


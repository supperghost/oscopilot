"""简易 MCP 客户端，通过 JSON-RPC over stdio 调用 SysOM MCP 等服务器。"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Dict

from ..config import MCPConfig, MCPServerConfig
from ..utils import ensure_no_invisible


@dataclass
class MCPClient:
    server_name: str
    server_cfg: MCPServerConfig

    def exec_tool(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        ensure_no_invisible(tool, field="tool")
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": tool,
            "params": params,
        }
        cmd = [self.server_cfg.command, *self.server_cfg.args]
        env = {**self.server_cfg.env, **{}}
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=self.server_cfg.cwd or None,
            env=env or None,
        )
        assert proc.stdin and proc.stdout
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        proc.stdin.close()
        proc.terminate()
        if not line:
            raise RuntimeError("MCP 服务器未返回数据")
        try:
            resp = json.loads(line)
        except json.JSONDecodeError as exc:  # noqa: BLE001
            raise RuntimeError(f"MCP 响应解析失败: {exc}") from exc
        if "error" in resp:
            raise RuntimeError(f"MCP 错误: {resp['error']}")
        return resp.get("result") or {}


def get_mcp_client(mcp_cfg: MCPConfig, name: str) -> MCPClient:
    if name not in mcp_cfg.servers:
        raise KeyError(f"未在配置中找到 MCP 服务器 {name}")
    return MCPClient(server_name=name, server_cfg=mcp_cfg.servers[name])


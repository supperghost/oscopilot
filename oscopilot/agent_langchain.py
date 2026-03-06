"""基于 LangChain 的 Agent 封装。

- 注册安全的系统信息与文件编辑工具
- 绑定到 OpenAI 兼容 LLM
- 示例：检查 CPU 负载并列出前 5 个高 CPU 进程
"""

from __future__ import annotations

from typing import Optional

from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from .context import AppContext
from .tools import system_info, files


def _build_tools(ctx: AppContext):
    @tool("check_cpu_and_top_processes")
    def check_cpu_and_top_processes() -> str:  # type: ignore[override]
        """检查 CPU 负载并列出前 5 个高 CPU 进程。"""
        return system_info.cpu_load_and_top_processes(ctx, limit=5)

    @tool(
        "append_hosts_mapping"
    )
    def append_hosts_mapping(ip: str, hostname: str) -> str:  # type: ignore[override]
        """向 /etc/hosts 追加一条 IP 与主机名映射（高风险操作，需审批与审计）。"""
        line = f"{ip} {hostname}"
        return files.append_line_with_approval(ctx, "/etc/hosts", line=line)

    return [check_cpu_and_top_processes, append_hosts_mapping]



def _build_agent(ctx: AppContext):
    llm = ChatOpenAI(
        base_url=ctx.config.llm.base_url,
        api_key=ctx.config.llm.api_key,
        model=ctx.config.llm.model,
        timeout=ctx.config.llm.timeout,
    )
    tools = _build_tools(ctx)

    system_prompt = (
        "你是一个 Linux OS Copilot 助手，专注于安全的系统诊断。"
        "在调用任何会修改系统状态的工具前，务必给出中文解释，并只调用已经注册的工具。"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    inner = create_tool_calling_agent(llm, tools, prompt)

    class SimpleAgent:
        """适配 create_tool_calling_agent 的 runnable，自动补充 intermediate_steps。"""

        def __init__(self, runnable):
            self._runnable = runnable

        def invoke(self, inputs, **kwargs):
            if "intermediate_steps" not in inputs:
                inputs = {**inputs, "intermediate_steps": []}
            return self._runnable.invoke(inputs, **kwargs)

    return SimpleAgent(inner)

def run_agent(ctx: AppContext, one_shot_prompt: Optional[str] = None) -> None:
    """启动 Agent，支持一次性指令或交互式对话。"""

    executor = _build_agent(ctx)

    if one_shot_prompt:
        result = executor.invoke({"input": text})
        # 兼容不同 langchain 版本的返回结构
        if isinstance(result, dict):
            print(result.get("output") or result)
        else:
            # list / str 等，直接打印
            print(result)
        return

    print("进入交互模式，输入 exit 退出。")
    while True:
        try:
            text = input("oscopilot> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            break
        result = executor.invoke({"input": text})
        # 兼容不同 langchain 版本的返回结构
        if isinstance(result, dict):
            print(result.get("output") or result)
        else:
            # list / str 等，直接打印
            print(result)
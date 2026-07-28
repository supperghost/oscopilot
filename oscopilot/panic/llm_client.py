"""独立 LLM 客户端 - 用于与 LLM 交互进行 panic 分析。

不依赖 LangChain，直接使用 HTTP API 调用 LLM。
"""

from __future__ import annotations

from typing import Dict, List, Optional

import requests


class LLMClientError(Exception):
    """LLM 客户端错误。"""


class LLMClient:
    """简易 LLM 客户端。

    用于与 OpenAI 兼容接口交互，支持多轮对话。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

        self._messages: List[Dict[str, str]] = []

    def add_system_prompt(self, prompt: str) -> None:
        """设置系统提示词。"""
        self._messages = [{"role": "system", "content": prompt}]

    def add_user_message(self, content: str) -> None:
        """添加用户消息。"""
        self._messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """添加助手消息。"""
        self._messages.append({"role": "assistant", "content": content})

    def clear_history(self) -> None:
        """清空对话历史。"""
        self._messages.clear()

    def chat(self, user_message: str, system_prompt: Optional[str] = None) -> str:
        """发送消息并获取回复。

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词（可选，若提供则重置对话）

        Returns:
            LLM 回复内容
        """
        if system_prompt:
            self._messages = [{"role": "system", "content": system_prompt}]

        self._messages.append({"role": "user", "content": user_message})

        try:
            response = requests.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": self._messages,
                    "temperature": 0.3,  # 低温度用于分析任务
                    "max_tokens": 4096,
                },
                timeout=self._timeout,
            )

            response.raise_for_status()
            data = response.json()

            assistant_message = data["choices"][0]["message"]["content"]
            self._messages.append({"role": "assistant", "content": assistant_message})

            return assistant_message

        except requests.exceptions.Timeout:
            raise LLMClientError("LLM 请求超时")
        except requests.exceptions.ConnectionError:
            raise LLMClientError("无法连接到 LLM 服务")
        except requests.exceptions.HTTPError as e:
            raise LLMClientError(f"LLM HTTP 错误: {e}")
        except (KeyError, IndexError) as e:
            raise LLMClientError(f"LLM 响应解析失败: {e}")
        except Exception as e:
            raise LLMClientError(f"LLM 调用异常: {e}")
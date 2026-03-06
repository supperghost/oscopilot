"""通用工具函数：输入净化、ID 生成等。"""

from __future__ import annotations

import re
import uuid
from typing import Iterable, List

# 零宽和控制类不可见字符范围（简化实现）
INVISIBLE_CHARS_RE = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2060-\u206F]")


class InputSanitizationError(ValueError):
    """输入中包含不可见字符等非法内容。"""


def ensure_no_invisible(text: str, field: str = "input") -> str:
    """确保字符串中不包含零宽等不可见字符，否则抛异常。

    该函数用于防御提示词注入中常见的零宽字符隐写。"""

    if INVISIBLE_CHARS_RE.search(text):
        raise InputSanitizationError(f"字段 {field} 含有不可见字符，已拒绝。")
    return text


def sanitize_str_list(values: Iterable[str], field: str = "args") -> List[str]:
    return [ensure_no_invisible(v, field=f"{field}[{i}]") for i, v in enumerate(values)]


def generate_session_id() -> str:
    return uuid.uuid4().hex


def generate_action_id() -> str:
    return uuid.uuid4().hex


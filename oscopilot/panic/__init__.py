"""panic 模块 - 内核 Panic 自动分析工具。

使用 crash 工具加载 vmcore，借助 LLM 多轮分析定位内核崩溃根因。
"""

from .analyzer import PanicAnalyzer

__all__ = ["PanicAnalyzer"]
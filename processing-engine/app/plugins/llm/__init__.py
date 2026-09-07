from __future__ import annotations

from app.plugins.llm.openai import OpenAIProvider
from app.plugins.registry import register

register("llm", "openai", OpenAIProvider)

__all__ = ["OpenAIProvider"]

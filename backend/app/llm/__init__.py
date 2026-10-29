from functools import lru_cache

from ..config import get_settings
from .base import LLMProvider


@lru_cache
def get_provider() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(s)
    from .mock import MockProvider
    return MockProvider()

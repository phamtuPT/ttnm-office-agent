"""Tạo provider theo cài đặt hiện tại. Đổi cài đặt → lần gọi sau dùng provider mới, không cần khởi động lại."""
from ..config import get_settings
from ..runtime_settings import RuntimeConfig
from .base import LLMProvider

_cache: dict[str, LLMProvider] = {}


def get_provider(cfg: RuntimeConfig) -> LLMProvider:
    key = cfg.model_dump_json(include={"provider", "models", "ollama_base_url", "api_keys"})
    if key not in _cache:
        _cache.clear()
        _cache[key] = _build(cfg)
    return _cache[key]


def _build(cfg: RuntimeConfig) -> LLMProvider:
    idle = get_settings().stream_idle_timeout_s
    m = cfg.models.get(cfg.provider)
    if cfg.provider == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(api_key=cfg.api_keys.get("gemini", ""), model=m.agent, lite_model=m.lite or m.agent,
                              fallback_model=m.fallback or m.agent, stt_model=m.stt or m.lite or m.agent,
                              idle_timeout=idle)
    if cfg.provider in ("openai", "ollama"):
        from .openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(
            name=cfg.provider, base_url=cfg.ollama_base_url if cfg.provider == "ollama" else None,
            api_key=cfg.api_keys.get(cfg.provider, ""), model=m.agent if m else "", lite_model=m.lite if m else "",
            stt_model=m.stt if m else "", idle_timeout=idle)
    from .mock import MockProvider
    return MockProvider()

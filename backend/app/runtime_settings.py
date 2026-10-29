"""Cài đặt đổi được lúc đang chạy: nhà cung cấp LLM, model, khoá API, ẩn danh PII.

Giá trị mặc định lấy từ .env; người dùng sửa qua /api/settings, lưu trong bảng app_settings.
Khoá API chỉ GHI được — API không bao giờ trả khoá về giao diện (chỉ báo có/không).
"""
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import get_settings
from .db import AppSetting

PROVIDERS = ("gemini", "openai", "ollama", "mock")
KEY = "runtime"


class ModelSet(BaseModel):
    agent: str = ""
    lite: str = ""
    fallback: str = ""
    stt: str = ""


class RuntimeConfig(BaseModel):
    provider: str
    models: dict[str, ModelSet]
    ollama_base_url: str
    pii_masking: bool
    api_keys: dict[str, str]


def defaults() -> RuntimeConfig:
    s = get_settings()
    return RuntimeConfig(
        provider=s.llm_provider,
        models={
            "gemini": ModelSet(agent=s.agent_model, lite=s.lite_model, fallback=s.fallback_model, stt=s.stt_model),
            "openai": ModelSet(agent=s.openai_model),
            "ollama": ModelSet(agent=s.ollama_model),
            "mock": ModelSet(agent="mock"),
        },
        ollama_base_url=s.ollama_base_url,
        pii_masking=s.pii_masking,
        api_keys={"gemini": s.gemini_api_key, "openai": s.openai_api_key},
    )


def load(db: Session) -> RuntimeConfig:
    cfg = defaults()
    row = db.get(AppSetting, KEY)
    if row:
        stored = row.value
        data = cfg.model_dump()
        for k in ("provider", "ollama_base_url", "pii_masking"):
            if k in stored:
                data[k] = stored[k]
        for p, m in stored.get("models", {}).items():
            data["models"].setdefault(p, {}).update({k: v for k, v in m.items() if v})
        data["api_keys"].update({k: v for k, v in stored.get("api_keys", {}).items() if v})
        cfg = RuntimeConfig.model_validate(data)
    return cfg


class SettingsPatch(BaseModel):
    provider: str | None = None
    models: dict[str, ModelSet] | None = None
    ollama_base_url: str | None = None
    pii_masking: bool | None = None
    api_keys: dict[str, str] | None = None  # "" = xoá khoá đã lưu (quay về .env)


def save(db: Session, patch: SettingsPatch) -> RuntimeConfig:
    if patch.provider is not None and patch.provider not in PROVIDERS:
        raise ValueError(f"Nhà cung cấp không hợp lệ, chọn một trong {PROVIDERS}")
    row = db.get(AppSetting, KEY) or AppSetting(key=KEY, value={})
    v = dict(row.value)
    for k in ("provider", "ollama_base_url", "pii_masking"):
        if getattr(patch, k) is not None:
            v[k] = getattr(patch, k)
    if patch.models:
        models = dict(v.get("models", {}))
        for p, m in patch.models.items():
            models[p] = {**models.get(p, {}), **m.model_dump()}
        v["models"] = models
    if patch.api_keys:
        keys = dict(v.get("api_keys", {}))
        for p, key in patch.api_keys.items():
            if key:
                keys[p] = key.strip()
            else:
                keys.pop(p, None)
        v["api_keys"] = keys
    row.value = v
    db.add(row)
    db.commit()
    return load(db)


def public_view(cfg: RuntimeConfig) -> dict:
    data = cfg.model_dump(exclude={"api_keys"})
    data["has_key"] = {p: bool(cfg.api_keys.get(p)) for p in ("gemini", "openai")}
    return data

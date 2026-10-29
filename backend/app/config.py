from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "gemini" khi chạy thật, "mock" để phát triển giao diện / chạy test không cần API key
    llm_provider: str = "mock"
    gemini_api_key: str = ""

    # Tên model đặt trong .env để đổi model / né đợt tăng giá mà không sửa code
    agent_model: str = "gemini-3.8-flash"
    lite_model: str = "gemini-3.5-flash-lite"
    fallback_model: str = "gemini-3.5-flash-lite"
    stt_model: str = "gemini-3.5-flash-lite"

    max_steps: int = 8
    tool_timeout_s: float = 30
    turn_timeout_s: float = 180

    storage_dir: Path = Path("./storage")
    database_url: str = "sqlite:///./storage/app.db"
    max_upload_mb: int = 20
    max_image_mb: int = 5
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

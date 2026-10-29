from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình khởi động (.env). Nhà cung cấp/model/khoá API đổi được lúc chạy qua /api/settings —
    giá trị ở đây chỉ là mặc định ban đầu."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # gemini | openai | ollama | mock ("mock" để làm giao diện / chạy test không cần API key)
    llm_provider: str = "mock"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434/v1"

    # Tên model đặt trong .env để đổi model / né đợt tăng giá mà không sửa code
    agent_model: str = "gemini-3.8-flash"
    lite_model: str = "gemini-3.5-flash-lite"
    fallback_model: str = "gemini-3.5-flash-lite"
    stt_model: str = "gemini-3.5-flash-lite"
    # Mức suy nghĩ của model agent Gemini: low | medium | high; trống = mặc định của model.
    # "low" giảm thời gian tới phản hồi đầu từ ~5,5 s xuống ~2,5 s (đo 29/10/2026) — xem docs/EVAL.md
    agent_thinking_level: str = "low"
    openai_model: str = ""
    ollama_model: str = ""

    pii_masking: bool = False

    max_steps: int = 10
    tool_timeout_s: float = 60
    turn_timeout_s: float = 300
    stream_idle_timeout_s: float = 60  # stream không nhận được gì quá lâu → coi là treo
    max_generations: int = 20  # số thế hệ sao lưu giữ lại cho mỗi tệp

    storage_dir: Path = Path("./storage")
    database_url: str = "sqlite:///./storage/app.db"
    max_upload_mb: int = 20
    max_image_mb: int = 10
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    soffice_path: str = ""  # để trống = tìm soffice/libreoffice trong PATH
    # Dịch vụ chạy mã phân tích dữ liệu (run_python) — container riêng, không có mạng. Trống = tắt tính năng.
    sandbox_url: str = ""
    sandbox_timeout_s: float = 60
    tesseract_path: str = ""  # OCR cục bộ để so sánh với vision LLM; trống = tìm trong PATH


@lru_cache
def get_settings() -> Settings:
    return Settings()

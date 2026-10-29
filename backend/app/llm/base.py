"""Giao diện chung cho mọi LLM. Agent loop chỉ làm việc qua lớp này.

Lịch sử hội thoại là list[dict] ở định dạng GỐC của provider (đã serialize JSON) để lưu DB
và gửi lại nguyên vẹn — bắt buộc với Gemini vì thought_signature.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Awaitable, Callable

OnText = Callable[[str], Awaitable[None]]


@dataclass
class ToolCall:
    id: str | None
    name: str
    args: dict


@dataclass
class TurnResult:
    text: str
    tool_calls: list[ToolCall]
    raw: dict  # tin nhắn của model, dạng gốc của provider, để nối vào lịch sử
    finish_reason: str | None = None
    usage: dict = field(default_factory=dict)


class LLMError(Exception):
    pass


class LLMProvider(ABC):
    @abstractmethod
    async def stream_turn(self, history: list[dict], system: str, tools: list[dict], on_text: OnText) -> TurnResult:
        """Gọi model một lần; chữ trả về được đẩy dần qua on_text."""

    @abstractmethod
    def user_message(self, text: str, images: list[tuple[bytes, str]]) -> dict:
        """Tạo tin nhắn người dùng (images: [(bytes, mime_type)])."""

    @abstractmethod
    def model_text_message(self, text: str) -> dict:
        """Tin nhắn chữ của model do hệ thống tự tạo (ví dụ ghi chú khi lượt bị dừng giữa chừng)."""

    @abstractmethod
    def tool_results_message(self, results: list[tuple[ToolCall, dict]]) -> dict:
        """Gói kết quả các tool để gửi lại cho model."""

    @abstractmethod
    async def quick(self, prompt: str) -> str:
        """Việc phụ rẻ tiền (đặt tên phiên, ...) bằng model lite."""

    @abstractmethod
    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        """Chuyển giọng nói thành văn bản."""

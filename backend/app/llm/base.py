"""Giao diện chung cho mọi LLM. Agent loop chỉ làm việc qua lớp này.

Lịch sử hội thoại là list[dict] ở định dạng GỐC của provider (`fmt`), lưu DB và gửi lại nguyên vẹn —
bắt buộc với Gemini vì thought_signature. Đổi provider giữa phiên → adopt_history() dựng lại từ chữ.
"""
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Awaitable, Callable

OnText = Callable[[str], Awaitable[None]]
Image = tuple[bytes, str]  # (dữ liệu, mime)


@dataclass
class ToolCall:
    id: str | None
    name: str
    args: dict
    error: str | None = None  # model trả tham số không phải JSON hợp lệ


@dataclass
class TurnResult:
    text: str
    tool_calls: list[ToolCall]
    raw: dict  # tin nhắn của model, dạng gốc của provider, để nối vào lịch sử
    finish_reason: str | None = None
    usage: dict = field(default_factory=dict)  # {"input_tokens", "output_tokens"}


@dataclass
class HistoryRow:
    role: str  # user | model | tool
    text: str
    fmt: str
    raw: dict


class LLMError(Exception):
    pass


async def with_idle_timeout(stream: AsyncIterator, timeout: float) -> AsyncIterator:
    """Lặp stream nhưng báo lỗi nếu quá `timeout` giây không nhận được gói nào (stream bị treo)."""
    it = stream.__aiter__()
    while True:
        try:
            yield await asyncio.wait_for(it.__anext__(), timeout)
        except StopAsyncIteration:
            return
        except asyncio.TimeoutError:
            raise LLMError(f"Mô hình không phản hồi trong {int(timeout)} giây")


class LLMProvider(ABC):
    fmt: str = ""  # định dạng lịch sử: gemini | openai | mock
    name: str = ""  # tên hiển thị của nhà cung cấp
    model: str = ""

    @abstractmethod
    async def stream_turn(self, history: list[dict], system: str, tools: list[dict], on_text: OnText) -> TurnResult:
        """Gọi model một lần; chữ trả về được đẩy dần qua on_text."""

    @abstractmethod
    def user_message(self, text: str, images: list[Image]) -> dict:
        """Tạo tin nhắn người dùng."""

    @abstractmethod
    def model_text_message(self, text: str) -> dict:
        """Tin nhắn chữ của model do hệ thống tự tạo (ví dụ ghi chú khi lượt bị dừng giữa chừng)."""

    @abstractmethod
    def tool_results_message(self, results: list[tuple[ToolCall, dict, list[Image]]]) -> dict:
        """Gói kết quả các tool (kèm ảnh nếu có) để gửi lại cho model."""

    @abstractmethod
    async def quick(self, prompt: str) -> str:
        """Việc phụ rẻ tiền (đặt tên phiên, ...) bằng model lite."""

    @abstractmethod
    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        """Chuyển giọng nói thành văn bản (dự phòng khi trình duyệt không có Web Speech API)."""

    def adopt_history(self, rows: list[HistoryRow]) -> list[dict]:
        if all(r.fmt == self.fmt for r in rows):
            return [r.raw for r in rows]
        # Lịch sử từ provider khác: chỉ giữ phần chữ, gộp các tin liên tiếp cùng vai
        merged: list[tuple[str, str]] = []
        for r in rows:
            if r.role == "tool" or not r.text.strip():
                continue
            if merged and merged[-1][0] == r.role:
                merged[-1] = (r.role, merged[-1][1] + "\n\n" + r.text)
            else:
                merged.append((r.role, r.text))
        return [self.user_message(t, []) if role == "user" else self.model_text_message(t) for role, t in merged]

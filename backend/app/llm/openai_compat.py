"""Provider theo chuẩn OpenAI Chat Completions — dùng cho cả OpenAI và Ollama (cục bộ hoặc cloud).

Ollama cung cấp API tương thích OpenAI tại http://<máy>:11434/v1, hỗ trợ tool calling và stream.
"""
import base64
import json

import openai
from openai import AsyncOpenAI

from .base import LLMError, LLMProvider, OnText, ToolCall, TurnResult, with_idle_timeout


def _content(text: str, images) -> str | list:
    if not images:
        return text
    parts = [{"type": "text", "text": text}] if text else []
    for data, mime in images:
        parts.append({"type": "image_url",
                      "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}})
    return parts


class OpenAICompatProvider(LLMProvider):
    fmt = "openai"

    def __init__(self, *, name: str, base_url: str | None, api_key: str, model: str, lite_model: str = "",
                 stt_model: str = "", idle_timeout: float = 60):
        if not model:
            raise LLMError(f"Chưa chọn model cho {name} — nhập trong Cài đặt")
        if name == "openai" and not api_key:
            raise LLMError("Chưa có khoá API OpenAI — nhập trong Cài đặt hoặc OPENAI_API_KEY trong .env")
        self.name, self.model = name, model
        self.lite_model = lite_model or model
        self.stt_model = stt_model
        self.base_url = base_url
        self.idle_timeout = idle_timeout
        # Ollama không cần khoá nhưng SDK bắt buộc có giá trị
        self.client = AsyncOpenAI(base_url=base_url or None, api_key=api_key or "ollama", max_retries=3)

    def _error(self, e: Exception) -> LLMError:
        if isinstance(e, openai.APIConnectionError):
            return LLMError(f"Không kết nối được {self.name} tại {self.base_url or 'api.openai.com'}")
        if isinstance(e, openai.APIStatusError):
            return LLMError(f"{self.name} lỗi {e.status_code}: {e.message}")
        return LLMError(f"{self.name} lỗi: {e}")

    @staticmethod
    def _flatten(history: list[dict]) -> list[dict]:
        out = []
        for h in history:
            out.extend(h["_multi"] if "_multi" in h else [h])
        return out

    async def stream_turn(self, history, system, tools, on_text: OnText) -> TurnResult:
        messages = [{"role": "system", "content": system}] + self._flatten(history)
        tool_specs = [{"type": "function", "function": t} for t in tools]
        text, calls, finish, usage = [], {}, None, {}
        try:
            stream = await self.client.chat.completions.create(
                model=self.model, messages=messages, tools=tool_specs, stream=True,
                stream_options={"include_usage": True})
            async for chunk in with_idle_timeout(stream, self.idle_timeout):
                if chunk.usage:
                    usage = {"input_tokens": chunk.usage.prompt_tokens or 0,
                             "output_tokens": chunk.usage.completion_tokens or 0}
                for choice in chunk.choices:
                    d = choice.delta
                    if d.content:
                        text.append(d.content)
                        await on_text(d.content)
                    for tc in d.tool_calls or []:
                        slot = calls.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                        slot["id"] = tc.id or slot["id"]
                        if tc.function:
                            slot["name"] += tc.function.name or ""
                            slot["args"] += tc.function.arguments or ""
                    finish = choice.finish_reason or finish
        except openai.OpenAIError as e:
            raise self._error(e) from e

        tool_calls = []
        for i, c in sorted(calls.items()):
            cid = c["id"] or f"call_{i}"
            try:
                tool_calls.append(ToolCall(cid, c["name"], json.loads(c["args"] or "{}")))
            except json.JSONDecodeError:
                tool_calls.append(ToolCall(cid, c["name"], {}, error=f"Tham số không phải JSON hợp lệ: {c['args'][:200]}"))
        full = "".join(text)
        raw: dict = {"role": "assistant", "content": full or None}
        if tool_calls:
            raw["tool_calls"] = [{"id": c.id, "type": "function",
                                  "function": {"name": c.name, "arguments": calls[i]["args"] or "{}"}}
                                 for i, c in zip(sorted(calls), tool_calls)]
        return TurnResult(full, tool_calls, raw, finish, usage)

    def user_message(self, text, images):
        return {"role": "user", "content": _content(text, images)}

    def model_text_message(self, text):
        return {"role": "assistant", "content": text}

    def tool_results_message(self, results):
        msgs = [{"role": "tool", "tool_call_id": c.id, "content": json.dumps(r, ensure_ascii=False)}
                for c, r, _ in results]
        # Tin nhắn "tool" chỉ chứa chữ → ảnh gửi kèm bằng một tin nhắn người dùng ngay sau
        images = [img for _, _, imgs in results for img in imgs]
        if images:
            msgs.append({"role": "user", "content": _content("Ảnh kết quả của công cụ vừa gọi:", images)})
        return {"_multi": msgs}

    async def quick(self, prompt: str) -> str:
        try:
            resp = await self.client.chat.completions.create(
                model=self.lite_model, messages=[{"role": "user", "content": prompt}])
        except openai.OpenAIError as e:
            raise self._error(e) from e
        return (resp.choices[0].message.content or "").strip()

    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        if self.name != "openai" or not self.stt_model:
            raise LLMError(f"{self.name} không có dịch vụ nhận dạng giọng nói — hãy dùng Chrome/Edge "
                           "(nhận dạng giọng nói của trình duyệt) hoặc chuyển sang Gemini")
        ext = mime_type.split("/")[-1].split(";")[0]
        try:
            r = await self.client.audio.transcriptions.create(
                model=self.stt_model, file=(f"voice.{ext}", audio, mime_type), language="vi")
        except openai.OpenAIError as e:
            raise self._error(e) from e
        return r.text.strip()

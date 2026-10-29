"""Gemini qua SDK google-genai. Chi tiết lựa chọn model và chi phí: docs/LLM_GEMINI.md."""
import asyncio
import logging

from google import genai
from google.genai import errors, types

from .base import LLMError, LLMProvider, OnText, ToolCall, TurnResult, with_idle_timeout

log = logging.getLogger(__name__)

RETRYABLE = {429, 500, 503, 504}
STT_PROMPT = ("Chép lại nguyên văn lời nói trong đoạn ghi âm (chủ yếu tiếng Việt). "
              "Chỉ trả về văn bản đã chép, không thêm giải thích.")


def _dump(content: types.Content) -> dict:
    # mode="json" mã hoá thought_signature (bytes) thành base64, model_validate giải mã lại
    return content.model_dump(mode="json", exclude_none=True)


class GeminiProvider(LLMProvider):
    fmt = "gemini"
    name = "gemini"

    def __init__(self, *, api_key: str, model: str, lite_model: str, fallback_model: str, stt_model: str,
                 idle_timeout: float = 60, thinking_level: str = ""):
        if not api_key:
            raise LLMError("Chưa có khoá API Gemini — nhập trong Cài đặt hoặc GEMINI_API_KEY trong .env")
        self.model, self.lite_model, self.fallback_model, self.stt_model = model, lite_model, fallback_model, stt_model
        self.idle_timeout = idle_timeout
        self.thinking_level = thinking_level.upper()
        self.client = genai.Client(api_key=api_key)

    async def _call(self, fn, *, streaming_started=lambda: False):
        """Thử lại khi quá tải/429, rồi chuyển sang model dự phòng. Không thử lại nếu đã stream chữ ra."""
        last: Exception | None = None
        for model in dict.fromkeys([self.model, self.fallback_model]):
            for attempt in range(3):
                try:
                    return await fn(model)
                except errors.APIError as e:
                    last = e
                    if e.code not in RETRYABLE or streaming_started():
                        raise LLMError(f"Gemini lỗi {e.code}: {e.message}") from e
                    log.warning("Gemini %s lỗi %s, thử lại lần %s", model, e.code, attempt + 1)
                    await asyncio.sleep(2 ** attempt)
        raise LLMError(f"Gemini đang quá tải, vui lòng thử lại sau ({last})")

    async def stream_turn(self, history, system, tools, on_text: OnText) -> TurnResult:
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(name=t["name"], description=t["description"],
                                          parameters_json_schema=t["parameters"]) for t in tools])],
            # Tự chạy vòng lặp để kịp sao lưu, stream tiến trình, đặt timeout, hỏi xác nhận
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        contents = [types.Content.model_validate(h) for h in history]
        emitted = False

        async def run(model: str):
            nonlocal emitted
            parts: list[types.Part] = []
            finish, usage = None, {}
            # Mức suy nghĩ chỉ áp cho model agent chính: model dự phòng có thể không hỗ trợ tham số này
            cfg = config.model_copy(update={"thinking_config": types.ThinkingConfig(
                thinking_level=self.thinking_level)}) if self.thinking_level and model == self.model else config
            stream = await self.client.aio.models.generate_content_stream(
                model=model, contents=contents, config=cfg)
            async for chunk in with_idle_timeout(stream, self.idle_timeout):
                if chunk.usage_metadata:
                    u = chunk.usage_metadata
                    usage = {"input_tokens": u.prompt_token_count or 0,
                             "output_tokens": (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)}
                if not chunk.candidates:
                    continue
                cand = chunk.candidates[0]
                finish = cand.finish_reason.name if cand.finish_reason else finish
                for p in (cand.content.parts if cand.content and cand.content.parts else []):
                    # Giữ mọi part (kể cả part rỗng chỉ chứa thought_signature) để gửi lại nguyên vẹn
                    parts.append(p)
                    if p.text and not p.thought:
                        emitted = True
                        await on_text(p.text)
            return parts, finish, usage

        parts, finish, usage = await self._call(run, streaming_started=lambda: emitted)
        content = types.Content(role="model", parts=parts)
        calls = [ToolCall(p.function_call.id, p.function_call.name, dict(p.function_call.args or {}))
                 for p in parts if p.function_call]
        text = "".join(p.text for p in parts if p.text and not p.thought)
        return TurnResult(text, calls, _dump(content), finish, usage)

    def user_message(self, text, images):
        parts = [types.Part.from_bytes(data=data, mime_type=mime) for data, mime in images]
        if text:
            parts.append(types.Part(text=text))
        return _dump(types.Content(role="user", parts=parts))

    def model_text_message(self, text):
        return _dump(types.Content(role="model", parts=[types.Part(text=text)]))

    def tool_results_message(self, results):
        parts = []
        for call, result, images in results:
            # Ảnh (ví dụ trang vừa render) đi kèm ngay trong function response — Gemini 3+ hỗ trợ
            img_parts = [types.FunctionResponsePart(inline_data=types.FunctionResponseBlob(mime_type=m, data=d))
                         for d, m in images] or None
            parts.append(types.Part(function_response=types.FunctionResponse(
                id=call.id, name=call.name, response=result, parts=img_parts)))
        return _dump(types.Content(role="user", parts=parts))

    async def quick(self, prompt: str) -> str:
        resp = await self.client.aio.models.generate_content(model=self.lite_model, contents=prompt)
        return (resp.text or "").strip()

    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        try:
            resp = await self.client.aio.models.generate_content(
                model=self.stt_model, contents=[types.Part.from_bytes(data=audio, mime_type=mime_type), STT_PROMPT])
        except errors.APIError as e:
            raise LLMError(f"Gemini lỗi {e.code}: {e.message}") from e
        return (resp.text or "").strip()

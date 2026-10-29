"""Gemini qua SDK google-genai. Chi tiết lựa chọn model và chi phí: docs/LLM_GEMINI.md."""
import asyncio
import logging

from google import genai
from google.genai import errors, types

from ..config import Settings
from .base import LLMError, LLMProvider, OnText, ToolCall, TurnResult

log = logging.getLogger(__name__)

RETRYABLE = {429, 500, 503, 504}
STT_PROMPT = ("Chép lại nguyên văn lời nói trong đoạn ghi âm (chủ yếu tiếng Việt). "
              "Chỉ trả về văn bản đã chép, không thêm giải thích.")


def _dump(content: types.Content) -> dict:
    # mode="json" mã hoá thought_signature (bytes) thành base64, model_validate giải mã lại
    return content.model_dump(mode="json", exclude_none=True)


class GeminiProvider(LLMProvider):
    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise LLMError("Thiếu GEMINI_API_KEY trong .env")
        self.s = settings
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def _call(self, fn, *, streaming_started=lambda: False):
        """Thử lại khi quá tải/429, rồi chuyển sang model dự phòng. Không thử lại nếu đã stream chữ ra."""
        models = [self.s.agent_model, self.s.fallback_model]
        last: Exception | None = None
        for model in dict.fromkeys(models):
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
            # Tự chạy vòng lặp để kịp snapshot, stream tiến trình, đặt timeout
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        contents = [types.Content.model_validate(h) for h in history]
        emitted = False

        async def run(model: str):
            nonlocal emitted
            parts: list[types.Part] = []
            finish, usage = None, {}
            stream = await self.client.aio.models.generate_content_stream(
                model=model, contents=contents, config=config)
            async for chunk in stream:
                if chunk.usage_metadata:
                    usage = chunk.usage_metadata.model_dump(exclude_none=True)
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
        return _dump(types.Content(role="user", parts=[
            types.Part(function_response=types.FunctionResponse(id=call.id, name=call.name, response=result))
            for call, result in results]))

    async def quick(self, prompt: str) -> str:
        resp = await self.client.aio.models.generate_content(model=self.s.lite_model, contents=prompt)
        return (resp.text or "").strip()

    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        resp = await self.client.aio.models.generate_content(
            model=self.s.stt_model,
            contents=[types.Part.from_bytes(data=audio, mime_type=mime_type), STT_PROMPT])
        return (resp.text or "").strip()

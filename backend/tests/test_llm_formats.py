"""Kiểm tra định dạng tin nhắn của từng provider mà không gọi mạng."""
import asyncio
from types import SimpleNamespace as NS

from google.genai import types

from app.llm.base import ToolCall
from app.llm.gemini import GeminiProvider
from app.llm.openai_compat import OpenAICompatProvider
from app.tools.registry import declarations


def _gemini():
    return GeminiProvider(api_key="test-key", model="m", lite_model="m", fallback_model="m", stt_model="m")


# ---------- Gemini ----------

def test_tool_declarations_are_valid_for_gemini():
    for d in declarations():
        fd = types.FunctionDeclaration(name=d["name"], description=d["description"],
                                       parameters_json_schema=d["parameters"])
        assert "$ref" not in str(fd.parameters_json_schema)


def test_gemini_history_roundtrip_keeps_thought_signature():
    model_msg = types.Content(role="model", parts=[types.Part(
        function_call=types.FunctionCall(id="c1", name="excel_inspect", args={"file": "a.xlsx"}),
        thought_signature=b"\x01\x02sig")])
    back = types.Content.model_validate(model_msg.model_dump(mode="json", exclude_none=True))
    assert back.parts[0].thought_signature == b"\x01\x02sig"


def test_gemini_user_and_tool_messages_with_images():
    p = _gemini()
    u = types.Content.model_validate(p.user_message("Đọc bảng này", [(b"\x89PNG", "image/png")]))
    assert u.role == "user" and u.parts[0].inline_data.mime_type == "image/png" and u.parts[1].text == "Đọc bảng này"

    t = types.Content.model_validate(p.tool_results_message(
        [(ToolCall("c1", "render_pages", {}), {"ok": True}, [(b"img", "image/png")])]))
    fr = t.parts[0].function_response
    assert fr.id == "c1" and fr.response == {"ok": True} and fr.parts[0].inline_data.data == b"img"


# ---------- OpenAI / Ollama ----------

def _chunk(content=None, tool_calls=None, finish=None, usage=None):
    choices = [NS(delta=NS(content=content, tool_calls=tool_calls), finish_reason=finish)] if (content or tool_calls or finish) else []
    return NS(choices=choices, usage=usage)


def _tc(index, id=None, name=None, args=None):
    return NS(index=index, id=id, function=NS(name=name, arguments=args))


class _FakeCompletions:
    def __init__(self, chunks):
        self.chunks, self.kwargs = chunks, None

    async def create(self, **kwargs):
        self.kwargs = kwargs

        async def gen():
            for c in self.chunks:
                yield c
        return gen()


def test_openai_stream_assembles_tool_calls_and_text():
    p = OpenAICompatProvider(name="ollama", base_url="http://localhost:11434/v1", api_key="", model="qwen")
    fake = _FakeCompletions([
        _chunk(content="Đang "), _chunk(content="làm"),
        _chunk(tool_calls=[_tc(0, id="a", name="excel_", args='{"file": ')]),
        _chunk(tool_calls=[_tc(0, name="inspect", args='"x.xlsx"}')]),
        _chunk(tool_calls=[_tc(1, id="b", name="list_files", args="{oops")]),
        _chunk(finish="tool_calls"),
        _chunk(usage=NS(prompt_tokens=50, completion_tokens=7)),
    ])
    p.client = NS(chat=NS(completions=fake))
    streamed = []

    async def on_text(t):
        streamed.append(t)

    r = asyncio.run(p.stream_turn([p.user_message("hi", [])], "sys", declarations()[:1], on_text))
    assert "".join(streamed) == r.text == "Đang làm"
    assert r.tool_calls[0].name == "excel_inspect" and r.tool_calls[0].args == {"file": "x.xlsx"}
    assert r.tool_calls[1].error and r.usage == {"input_tokens": 50, "output_tokens": 7}
    assert fake.kwargs["messages"][0] == {"role": "system", "content": "sys"}
    assert r.raw["tool_calls"][0]["function"]["arguments"] == '{"file": "x.xlsx"}'


def test_openai_tool_results_flatten_with_images():
    p = OpenAICompatProvider(name="openai", base_url=None, api_key="k", model="m")
    msg = p.tool_results_message([(ToolCall("a", "render_pages", {}), {"ok": True}, [(b"img", "image/png")])])
    flat = p._flatten([msg])
    assert flat[0] == {"role": "tool", "tool_call_id": "a", "content": '{"ok": true}'}
    assert flat[1]["role"] == "user" and flat[1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_gemini_thinking_level_only_on_agent_model():
    from google.genai import errors
    p = GeminiProvider(api_key="k", model="main", lite_model="lite", fallback_model="backup", stt_model="lite",
                       thinking_level="low")
    seen = []

    async def fake_stream(model, contents, config):
        seen.append((model, config.thinking_config.thinking_level if config.thinking_config else None))
        if model == "main":
            raise errors.APIError(503, {"error": {"message": "quá tải", "status": "UNAVAILABLE"}})

        async def gen():
            yield types.GenerateContentResponse(candidates=[types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text="ok")]))])
        return gen()

    p.client = NS(aio=NS(models=NS(generate_content_stream=fake_stream)))
    import app.llm.gemini as gm
    real_sleep = gm.asyncio.sleep
    gm.asyncio.sleep = lambda s: real_sleep(0)
    try:
        async def noop(_t):
            pass
        r = asyncio.run(p.stream_turn([p.user_message("hi", [])], "sys", [], noop))
    finally:
        gm.asyncio.sleep = real_sleep
    assert r.text == "ok"
    assert seen[0] == ("main", types.ThinkingLevel.LOW) and seen[-1] == ("backup", None)

"""Kiểm tra định dạng tin nhắn Gemini mà không gọi mạng."""
from google.genai import types

from app.config import Settings
from app.llm.base import ToolCall
from app.llm.gemini import GeminiProvider
from app.tools.registry import declarations


def _provider():
    return GeminiProvider(Settings(gemini_api_key="test-key", llm_provider="gemini"))


def test_tool_declarations_are_valid_for_gemini():
    for d in declarations():
        fd = types.FunctionDeclaration(name=d["name"], description=d["description"],
                                       parameters_json_schema=d["parameters"])
        assert "$ref" not in str(fd.parameters_json_schema)


def test_history_roundtrip_keeps_thought_signature():
    model_msg = types.Content(role="model", parts=[types.Part(
        function_call=types.FunctionCall(id="c1", name="excel_inspect", args={"file": "a.xlsx"}),
        thought_signature=b"\x01\x02sig")])
    raw = model_msg.model_dump(mode="json", exclude_none=True)
    back = types.Content.model_validate(raw)
    assert back.parts[0].thought_signature == b"\x01\x02sig"


def test_user_and_tool_messages():
    p = _provider()
    u = types.Content.model_validate(p.user_message("Đọc bảng này", [(b"\x89PNG", "image/png")]))
    assert u.role == "user" and u.parts[0].inline_data.mime_type == "image/png" and u.parts[1].text == "Đọc bảng này"

    t = types.Content.model_validate(p.tool_results_message([(ToolCall("c1", "list_files", {}), {"ok": True})]))
    assert t.parts[0].function_response.id == "c1"
    assert t.parts[0].function_response.response == {"ok": True}

"""Vòng lặp agent: model → tool → model → ... cho đến khi model trả lời bằng chữ.

Sự kiện gửi ra qua `emit` (đặc tả: docs/API.md):
  message.delta, tool.start, tool.result, tool.error, file.changed, message.done
"""
from typing import Awaitable, Callable

from ..llm.base import LLMProvider
from ..tools.executor import ToolExecutor
from ..tools.registry import declarations
from .prompts import SYSTEM_PROMPT

Emit = Callable[[dict], Awaitable[None]]


class StepLimitError(Exception):
    pass


async def run_turn(*, provider: LLMProvider, executor: ToolExecutor, history: list[dict], user_raw: dict,
                   emit: Emit, max_steps: int, out: list[tuple[str, str, dict]]) -> None:
    """Chạy một lượt chat. Các mục lịch sử mới được nối vào `out` dạng (role, text, raw).

    `out` luôn ở trạng thái hợp lệ để lưu: lời gọi tool của model chỉ được nối vào cùng với kết quả,
    nên nếu lượt bị huỷ giữa chừng thì lịch sử không có function_call nào thiếu function_response.
    """
    hist = history + [user_raw]
    tools = declarations()

    async def on_text(t: str) -> None:
        await emit({"type": "message.delta", "text": t})

    for _ in range(max_steps):
        turn = await provider.stream_turn(hist, SYSTEM_PROMPT, tools, on_text)

        if not turn.tool_calls:
            text, raw = turn.text, turn.raw
            if not text.strip():
                text = f"(Model không trả lời, lý do: {turn.finish_reason or 'không rõ'})"
                raw = provider.model_text_message(text)
            out.append(("model", text, raw))
            await emit({"type": "message.done", "text": text, "usage": turn.usage})
            return

        results = []
        for call in turn.tool_calls:
            await emit({"type": "tool.start", "id": call.id, "name": call.name, "args": call.args})
            r = await executor.run(call.name, call.args)
            await emit({"type": "tool.result" if r.ok else "tool.error", "id": call.id, "name": call.name,
                        "result": r.for_model()})
            if r.ok and r.diff is not None:
                await emit({"type": "file.changed", "file_id": r.file_id, "file_name": r.file_name,
                            "version": r.version, "summary": r.summary, "diff": r.diff})
            results.append((call, r.for_model()))

        tool_raw = provider.tool_results_message(results)
        out += [("model", turn.text, turn.raw), ("tool", "", tool_raw)]
        hist += [turn.raw, tool_raw]

    raise StepLimitError(f"Đã vượt quá {max_steps} bước xử lý trong một lượt")

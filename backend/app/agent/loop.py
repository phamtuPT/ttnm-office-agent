"""Vòng lặp agent (ReAct tự cài đặt): model → tool → model → ... cho đến khi model trả lời bằng chữ.

Sự kiện gửi ra qua `emit` (đặc tả: docs/API.md):
  message.delta, tool.start, tool.result, tool.error, file.changed, message.done
"""
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from ..llm.base import LLMProvider
from ..privacy.pii import Anonymizer
from ..tools.executor import ToolExecutor, ToolResult
from ..tools.registry import declarations

Emit = Callable[[dict], Awaitable[None]]


class StepLimitError(Exception):
    pass


@dataclass
class TurnStats:
    started: float = field(default_factory=time.monotonic)
    first_token_ms: int | None = None
    steps: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


async def run_turn(*, provider: LLMProvider, executor: ToolExecutor, history: list[dict], user_raw: dict,
                   system: str, emit: Emit, max_steps: int, out: list[tuple[str, str, dict]],
                   pii: Anonymizer | None = None, stats: TurnStats | None = None) -> None:
    """Chạy một lượt chat. Các mục lịch sử mới được nối vào `out` dạng (role, text hiển thị, raw).

    `out` luôn ở trạng thái hợp lệ để lưu: lời gọi tool của model chỉ được nối vào cùng với kết quả,
    nên nếu lượt bị huỷ giữa chừng thì lịch sử không có function_call nào thiếu function_response.
    Với ẩn danh PII: raw gửi cho LLM là bản đã che, text hiển thị và tham số tool là bản thật.
    """
    stats = stats or TurnStats()
    hist = history + [user_raw]
    tools = declarations()
    show = pii.unmask_text if pii else (lambda s: s)

    async def on_text(t: str) -> None:
        if stats.first_token_ms is None:
            stats.first_token_ms = int((time.monotonic() - stats.started) * 1000)
        await emit({"type": "message.delta", "text": show(t)})

    for _ in range(max_steps):
        stats.steps += 1
        turn = await provider.stream_turn(hist, system, tools, on_text)
        stats.input_tokens += turn.usage.get("input_tokens", 0)
        stats.output_tokens += turn.usage.get("output_tokens", 0)

        if not turn.tool_calls:
            text, raw = turn.text, turn.raw
            if not text.strip():
                text = f"(Model không trả lời, lý do: {turn.finish_reason or 'không rõ'})"
                raw = provider.model_text_message(text)
            out.append(("model", show(text), raw))
            await emit({"type": "message.done", "text": show(text)})
            return

        results = []
        for call in turn.tool_calls:
            args = pii.unmask(call.args) if pii else call.args
            await emit({"type": "tool.start", "id": call.id, "name": call.name, "args": args})
            stats.tool_calls += 1
            r = (ToolResult(False, {"error": call.error}) if call.error
                 else await executor.run(call.name, args))
            stats.tool_errors += 0 if r.ok else 1
            shown = r.for_model()
            await emit({"type": "tool.result" if r.ok else "tool.error", "id": call.id, "name": call.name,
                        "result": shown})
            for c in r.changes:
                await emit({"type": "file.changed", "file_id": c.file_id, "file_name": c.file_name,
                            "version": c.version, "summary": c.summary, "diff": c.diff})
            results.append((call, pii.mask(shown) if pii else shown, r.images))

        tool_raw = provider.tool_results_message(results)
        out += [("model", show(turn.text), turn.raw), ("tool", "", tool_raw)]
        hist += [turn.raw, tool_raw]

    raise StepLimitError(f"Đã vượt quá {max_steps} bước xử lý trong một lượt")

import asyncio

import pytest

from app.agent.loop import StepLimitError, run_turn
from app.llm.mock import MockProvider
from app.tools.executor import ToolExecutor
from app.versioning import store

from .conftest import xlsx_bytes


async def _always(_n, _a):
    return True


def _run(provider, executor, max_steps=8):
    events, out = [], []

    async def emit(e):
        events.append(e)

    asyncio.run(run_turn(provider=provider, executor=executor, history=[],
                         user_raw=provider.user_message("Tính tổng", []), emit=emit, max_steps=max_steps, out=out))
    return events, out


def test_tool_then_answer(db, chat):
    f = store.create_file(db, chat.id, "a.xlsx", xlsx_bytes())
    provider = MockProvider([
        {"tool_calls": [{"name": "excel_write_cells",
                         "args": {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "B5", "value": "=SUM(B2:B4)"}]}}]},
        {"text": "Đã thêm tổng vào ô B5."},
    ])
    events, out = _run(provider, ToolExecutor(db, chat.id, _always))

    types = [e["type"] for e in events]
    assert types[:3] == ["tool.start", "tool.result", "file.changed"]
    assert types[-1] == "message.done" and events[-1]["text"] == "Đã thêm tổng vào ô B5."
    assert [r for r, _, _ in out] == ["model", "tool", "model"]
    assert f.current_version == 2


def test_tool_error_goes_back_to_model(db, chat):
    store.create_file(db, chat.id, "b.xlsx", xlsx_bytes())
    provider = MockProvider([
        {"tool_calls": [{"name": "excel_inspect", "args": {"file": "sai-ten.xlsx"}}]},
        {"text": "Không tìm thấy tệp."},
    ])
    events, out = _run(provider, ToolExecutor(db, chat.id, _always))
    assert events[1]["type"] == "tool.error"
    assert out[1][2]["results"][0]["result"]["ok"] is False


def test_step_limit(db, chat):
    provider = MockProvider([{"tool_calls": [{"name": "list_files"}]}] * 3)
    with pytest.raises(StepLimitError):
        _run(provider, ToolExecutor(db, chat.id, _always), max_steps=3)

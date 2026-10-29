import asyncio

import pytest

from app.agent.loop import StepLimitError, TurnStats, run_turn
from app.agent.prompts import PPTX_GUIDE, system_prompt
from app.llm.base import HistoryRow
from app.llm.mock import MockProvider
from app.privacy.pii import Anonymizer
from app.tools.executor import ToolExecutor
from app.versioning import store

from .conftest import xlsx_bytes


async def _always(_n, _a):
    return True


def _run(provider, executor, max_steps=8, pii=None, text="Tính tổng"):
    events, out, stats = [], [], TurnStats()

    async def emit(e):
        events.append(e)

    user = pii.mask_text(text) if pii else text
    asyncio.run(run_turn(provider=provider, executor=executor, history=[], system="sys",
                         user_raw=provider.user_message(user, []), emit=emit, max_steps=max_steps, out=out,
                         pii=pii, stats=stats))
    return events, out, stats


def test_tool_then_answer(db, chat):
    f = store.create_file(db, chat.id, "a.xlsx", xlsx_bytes())
    provider = MockProvider([
        {"text": "① Ghi tổng → ② Báo lại", "tool_calls": [{"name": "excel_write_cells",
         "args": {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "B5", "value": "=SUM(B2:B4)"}]}}]},
        {"text": "Đã thêm tổng vào ô B5."},
    ])
    events, out, stats = _run(provider, ToolExecutor(db, chat.id, _always, turn_id="t1"))

    types = [e["type"] for e in events if e["type"] != "message.delta"]
    assert types == ["tool.start", "tool.result", "file.changed", "message.done"]
    assert events[-1]["text"] == "Đã thêm tổng vào ô B5."
    assert [r for r, _, _ in out] == ["model", "tool", "model"]
    assert stats.steps == 2 and stats.tool_calls == 1 and stats.first_token_ms is not None
    assert f.current_version == 2


def test_tool_error_goes_back_to_model(db, chat):
    store.create_file(db, chat.id, "b.xlsx", xlsx_bytes())
    provider = MockProvider([
        {"tool_calls": [{"name": "excel_inspect", "args": {"file": "sai-ten.xlsx"}}]},
        {"text": "Không tìm thấy tệp."},
    ])
    events, out, stats = _run(provider, ToolExecutor(db, chat.id, _always))
    assert events[1]["type"] == "tool.error" and stats.tool_errors == 1
    assert out[1][2]["results"][0]["result"]["ok"] is False


def test_step_limit(db, chat):
    provider = MockProvider([{"tool_calls": [{"name": "list_files"}]}] * 3)
    with pytest.raises(StepLimitError):
        _run(provider, ToolExecutor(db, chat.id, _always), max_steps=3)


def test_pii_never_reaches_model_but_reaches_file(db, chat):
    f = store.create_file(db, chat.id, "kh.xlsx", xlsx_bytes())
    pii = Anonymizer()
    provider = MockProvider([
        {"tool_calls": [{"name": "excel_write_cells", "args": {
            "file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "C1", "value": "⟦EMAIL_1⟧"}]}}]},
        {"text": "Đã ghi ⟦EMAIL_1⟧ vào C1."},
    ])
    events, out, _ = _run(provider, ToolExecutor(db, chat.id, _always), pii=pii, text="Ghi a.b@cty.vn vào C1")
    import openpyxl
    assert openpyxl.load_workbook(store.working_path(f))["Doanh thu"]["C1"].value == "a.b@cty.vn"
    assert events[-1]["text"] == "Đã ghi a.b@cty.vn vào C1."  # người dùng thấy giá trị thật
    assert "a.b@cty.vn" not in str([raw for _, _, raw in out])  # model chỉ thấy nhãn


def test_pptx_guide_only_when_relevant():
    assert PPTX_GUIDE not in system_prompt("Tính tổng cột B", [], "a.xlsx")
    assert PPTX_GUIDE in system_prompt("Làm 5 slide giới thiệu", [], None)
    assert PPTX_GUIDE in system_prompt("Sửa chỗ này", [], "bai.pptx")


def test_history_from_other_provider_is_rebuilt_from_text():
    rows = [HistoryRow("user", "Xin chào", "gemini", {"parts": []}),
            HistoryRow("model", "", "gemini", {"parts": []}),
            HistoryRow("tool", "", "gemini", {"parts": []}),
            HistoryRow("model", "Chào bạn", "gemini", {"parts": []})]
    hist = MockProvider().adopt_history(rows)
    assert hist == [{"role": "user", "text": "Xin chào", "images": 0},
                    {"role": "model", "text": "Chào bạn", "tool_calls": []}]

import asyncio

import openpyxl
from docx import Document
from pptx import Presentation

from app.tools.executor import ToolExecutor
from app.tools.registry import Selection
from app.versioning import store

from .conftest import docx_bytes, pptx_bytes, xlsx_bytes


async def _always(_name, _args):
    return True


async def _never(_name, _args):
    return False


def run(executor, name, args):
    return asyncio.run(executor.run(name, args))


def test_excel_inspect_and_write_creates_version(db, chat):
    f = store.create_file(db, chat.id, "bao cao.xlsx", xlsx_bytes())
    ex = ToolExecutor(db, chat.id, _always)

    r = run(ex, "excel_inspect", {"file": f.name})
    assert r.ok and r.data["sheets"][0]["name"] == "Doanh thu"

    r = run(ex, "excel_write_cells", {"file": f.name, "sheet": "Doanh thu",
                                      "cells": [{"ref": "B5", "value": "=SUM(B2:B4)"}, {"ref": "A5", "value": "Tổng"}]})
    assert r.ok and r.version == 2
    assert r.diff["cells_total"] == 2
    assert openpyxl.load_workbook(store.working_path(f))["Doanh thu"]["B5"].value == "=SUM(B2:B4)"


def test_undo_redo(db, chat):
    f = store.create_file(db, chat.id, "u.xlsx", xlsx_bytes())
    ex = ToolExecutor(db, chat.id, _always)
    run(ex, "excel_write_cells", {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "B2", "value": 999}]})

    store.undo(db, f)
    assert openpyxl.load_workbook(store.working_path(f))["Doanh thu"]["B2"].value == 100
    store.redo(db, f)
    assert openpyxl.load_workbook(store.working_path(f))["Doanh thu"]["B2"].value == 999


def test_write_after_undo_drops_redo_branch(db, chat):
    f = store.create_file(db, chat.id, "b.xlsx", xlsx_bytes())
    ex = ToolExecutor(db, chat.id, _always)
    args = {"file": f.name, "sheet": "Doanh thu"}
    run(ex, "excel_write_cells", {**args, "cells": [{"ref": "B2", "value": 1}]})
    store.undo(db, f)
    r = run(ex, "excel_write_cells", {**args, "cells": [{"ref": "B2", "value": 2}]})
    assert r.version == 2
    assert [v.number for v in f.versions] == [1, 2]


def test_selection_blocks_writes_outside(db, chat):
    f = store.create_file(db, chat.id, "s.xlsx", xlsx_bytes())
    ex = ToolExecutor(db, chat.id, _always, Selection(file=f.name, sheet="Doanh thu", range="B2:B4"))
    r = run(ex, "excel_write_cells", {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "C2", "value": 1}]})
    assert not r.ok and "ngoài vùng" in r.data["error"]
    assert f.current_version == 1


def test_errors_are_returned_to_model(db, chat):
    f = store.create_file(db, chat.id, "e.xlsx", xlsx_bytes())
    ex = ToolExecutor(db, chat.id, _always)
    assert "Không có sheet" in run(ex, "excel_read_range", {"file": f.name, "sheet": "X", "range": "A1"}).data["error"]
    assert "Tham số không hợp lệ" in run(ex, "excel_write_cells", {"file": f.name}).data["error"]
    assert "Không có tool" in run(ex, "khong_ton_tai", {}).data["error"]
    assert "Không có tệp" in run(ex, "excel_inspect", {"file": "nope.xlsx"}).data["error"]


def test_destructive_needs_confirmation(db, chat):
    f = store.create_file(db, chat.id, "d.xlsx", xlsx_bytes())
    r = run(ToolExecutor(db, chat.id, _never), "excel_delete_sheet", {"file": f.name, "sheet": "Ghi chú"})
    assert not r.ok and "từ chối" in r.data["error"]
    r = run(ToolExecutor(db, chat.id, _always), "excel_delete_sheet", {"file": f.name, "sheet": "Ghi chú"})
    assert r.ok and r.diff["sheets_removed"] == ["Ghi chú"]


def test_word_replace_and_insert(db, chat):
    f = store.create_file(db, chat.id, "w.docx", docx_bytes())
    ex = ToolExecutor(db, chat.id, _always)
    assert run(ex, "word_inspect", {"file": f.name}).data["total_paragraphs"] == 3
    run(ex, "word_replace_paragraph", {"file": f.name, "index": 1, "text": "Đoạn đã sửa."})
    r = run(ex, "word_insert_paragraph", {"file": f.name, "after_index": 2, "text": "Kết luận", "style": "Heading 2"})
    assert r.ok and r.version == 3
    paras = Document(store.working_path(f)).paragraphs
    assert [p.text for p in paras] == ["Báo cáo", "Đoạn đã sửa.", "Đoạn hai.", "Kết luận"]
    assert paras[3].style.name == "Heading 2"


def test_pptx_set_text(db, chat):
    f = store.create_file(db, chat.id, "p.pptx", pptx_bytes())
    ex = ToolExecutor(db, chat.id, _always)
    assert run(ex, "pptx_inspect", {"file": f.name}).data["slides"][0]["shapes"][0]["text"] == "Tiêu đề"
    r = run(ex, "pptx_set_text", {"file": f.name, "slide": 0, "shape": 1, "text": "Dòng 1\nDòng 2"})
    assert r.ok and r.diff["slides"][0]["after"] == "Tiêu đề\nDòng 1\nDòng 2"
    assert Presentation(store.working_path(f)).slides[0].placeholders[1].text_frame.text == "Dòng 1\nDòng 2"


def test_unchanged_write_warns_model(db, chat):
    f = store.create_file(db, chat.id, "n.xlsx", xlsx_bytes())
    r = run(ToolExecutor(db, chat.id, _always), "excel_write_cells",
            {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "B2", "value": 100}]})
    assert r.ok and "warning" in r.for_model() and r.version == 1

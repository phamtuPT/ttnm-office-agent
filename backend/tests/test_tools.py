import asyncio

import openpyxl
from docx import Document
from pptx import Presentation

from app.tools.executor import ToolExecutor
from app.tools.registry import Selection
from app.versioning import store

from .conftest import docx_bytes, png_bytes, pptx_bytes, xlsx_bytes


async def _always(_name, _args):
    return True


async def _never(_name, _args):
    return False


def run(executor, name, args):
    return asyncio.run(executor.run(name, args))


def ws_of(f, sheet="Doanh thu"):
    return openpyxl.load_workbook(store.working_path(f))[sheet]


# ---------- Excel ----------

def test_excel_inspect_and_write(db, chat):
    f = store.create_file(db, chat.id, "bao cao.xlsx", xlsx_bytes())
    ex = ToolExecutor(db, chat.id, _always, turn_id="t1")
    assert run(ex, "excel_inspect", {"file": f.name}).data["sheets"][0]["name"] == "Doanh thu"

    r = run(ex, "excel_write_cells", {"file": f.name, "sheet": "Doanh thu",
                                      "cells": [{"ref": "B5", "value": "=SUM(B2:B4)"}, {"ref": "A5", "value": "Tổng"}]})
    assert r.ok and r.changes[0].version == 2 and r.changes[0].diff["values_total"] == 2
    assert ws_of(f)["B5"].value == "=SUM(B2:B4)"


def test_overwrite_warning(db, chat):
    f = store.create_file(db, chat.id, "o.xlsx", xlsx_bytes())
    r = run(ToolExecutor(db, chat.id, _always), "excel_write_cells",
            {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "B2", "value": 5}, {"ref": "C2", "value": 1}]})
    assert r.data["overwritten"] == [{"ref": "B2", "old": 100}]


def test_format_and_conditional_are_versioned(db, chat):
    f = store.create_file(db, chat.id, "fmt.xlsx", xlsx_bytes())
    ex = ToolExecutor(db, chat.id, _always)
    r = run(ex, "excel_format_range", {"file": f.name, "sheet": "Doanh thu", "range": "B2:B4", "bold": True})
    assert r.ok and r.changes and r.changes[0].diff["formats_total"] == 3
    r = run(ex, "excel_conditional_format", {"file": f.name, "sheet": "Doanh thu", "range": "B2:B4",
                                             "operator": "lessThan", "value": 0, "font_color": "C00000"})
    assert r.ok and r.changes[0].diff["conditional"][0]["after"] == 1


def test_native_chart(db, chat):
    f = store.create_file(db, chat.id, "c.xlsx", xlsx_bytes())
    r = run(ToolExecutor(db, chat.id, _always), "excel_add_chart",
            {"file": f.name, "sheet": "Doanh thu", "chart_type": "column", "data_range": "B1:B4",
             "categories_range": "A2:A4", "title": "Doanh thu"})
    assert r.ok and r.changes[0].diff["charts"] == [{"sheet": "Doanh thu", "before": 0, "after": 1}]
    assert len(ws_of(f)._charts) == 1


def test_create_workbook(db, chat):
    ex = ToolExecutor(db, chat.id, _always, turn_id="t1")
    r = run(ex, "excel_create_workbook", {"file": "moi.xlsx", "sheets": [
        {"name": "DT", "rows": [["Tháng", "Tiền"], [1, 10], [2, 20], ["Tổng", "=SUM(B2:B3)"]]}]})
    assert r.ok and r.changes[0].file_name == "moi.xlsx"
    assert run(ex, "excel_create_workbook", {"file": "moi.xlsx", "sheets": [{"name": "X"}]}).ok is False
    assert "đuôi" in run(ex, "excel_create_workbook", {"file": "moi.docx", "sheets": [{"name": "X"}]}).data["error"]


# ---------- Phiên bản / hoàn tác ----------

def test_changes_in_one_request_share_a_version(db, chat):
    f = store.create_file(db, chat.id, "turn.xlsx", xlsx_bytes())
    ex = ToolExecutor(db, chat.id, _always, turn_id="t1")
    args = {"file": f.name, "sheet": "Doanh thu"}
    run(ex, "excel_write_cells", {**args, "cells": [{"ref": "B2", "value": 1}]})
    r = run(ex, "excel_write_cells", {**args, "cells": [{"ref": "B3", "value": 2}]})
    assert r.changes[0].version == 2 and r.changes[0].diff["values_total"] == 2  # gộp với bước trước

    store.undo(db, f)  # một nhấp hoàn tác cả yêu cầu
    assert ws_of(f)["B2"].value == 100 and ws_of(f)["B3"].value == 150
    store.redo(db, f)
    assert ws_of(f)["B2"].value == 1 and ws_of(f)["B3"].value == 2


def test_write_after_undo_drops_redo_branch(db, chat):
    f = store.create_file(db, chat.id, "b.xlsx", xlsx_bytes())
    args = {"file": f.name, "sheet": "Doanh thu"}
    run(ToolExecutor(db, chat.id, _always, turn_id="t1"), "excel_write_cells", {**args, "cells": [{"ref": "B2", "value": 1}]})
    store.undo(db, f)
    r = run(ToolExecutor(db, chat.id, _always, turn_id="t2"), "excel_write_cells", {**args, "cells": [{"ref": "B2", "value": 2}]})
    assert r.changes[0].version == 2 and [v.number for v in f.versions] == [1, 2]


def test_restore_is_itself_undoable(db, chat):
    f = store.create_file(db, chat.id, "r.xlsx", xlsx_bytes())
    run(ToolExecutor(db, chat.id, _always, turn_id="t1"), "excel_write_cells",
        {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "B2", "value": 7}]})
    store.restore(db, f, 1)
    assert f.current_version == 3 and ws_of(f)["B2"].value == 100
    store.undo(db, f)
    assert ws_of(f)["B2"].value == 7


def test_keeps_limited_generations(db, chat, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "max_generations", 3)
    f = store.create_file(db, chat.id, "g.xlsx", xlsx_bytes())
    for i in range(5):
        run(ToolExecutor(db, chat.id, _always, turn_id=f"t{i}"), "excel_write_cells",
            {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "B2", "value": i + 1000}]})
    assert [v.number for v in f.versions] == [4, 5, 6]


def test_failed_write_leaves_file_untouched(db, chat, monkeypatch):
    from app.tools import registry
    f = store.create_file(db, chat.id, "a.xlsx", xlsx_bytes())
    before = store.working_path(f).read_bytes()

    def boom(args, ctx):
        ctx.path.write_bytes(b"hong")  # ghi dở rồi lỗi
        raise RuntimeError("giữa chừng")
    monkeypatch.setattr(registry.REGISTRY["excel_write_cells"], "handler", boom)
    r = run(ToolExecutor(db, chat.id, _always), "excel_write_cells",
            {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "B2", "value": 1}]})
    assert not r.ok and store.working_path(f).read_bytes() == before and f.current_version == 1
    assert not list(store.working_path(f).parent.glob(".tmp-*"))


def test_undo_last_request_tool(db, chat):
    x = store.create_file(db, chat.id, "x.xlsx", xlsx_bytes())
    w = store.create_file(db, chat.id, "w.docx", docx_bytes())
    ex = ToolExecutor(db, chat.id, _always, turn_id="t1")
    run(ex, "excel_write_cells", {"file": x.name, "sheet": "Doanh thu", "cells": [{"ref": "B2", "value": 1}]})
    run(ex, "word_replace_paragraph", {"file": w.name, "index": 1, "text": "Mới"})
    r = run(ToolExecutor(db, chat.id, _always, turn_id="t2"), "undo_last_request", {})
    assert r.ok and sorted(c.file_name for c in r.changes) == ["w.docx", "x.xlsx"]
    assert ws_of(x)["B2"].value == 100 and Document(store.working_path(w)).paragraphs[1].text == "Đoạn một."


# ---------- Kiểm tra an toàn ----------

def test_selection_blocks_writes_outside(db, chat):
    f = store.create_file(db, chat.id, "s.xlsx", xlsx_bytes())
    ex = ToolExecutor(db, chat.id, _always, Selection(file=f.name, sheet="Doanh thu", range="B2:B4"))
    r = run(ex, "excel_write_cells", {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "C2", "value": 1}]})
    assert not r.ok and "ngoài vùng" in r.data["error"] and f.current_version == 1


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
    assert r.ok and r.changes[0].diff["sheets_removed"] == ["Ghi chú"]


def test_unchanged_write_warns_model(db, chat):
    f = store.create_file(db, chat.id, "n.xlsx", xlsx_bytes())
    r = run(ToolExecutor(db, chat.id, _always), "excel_write_cells",
            {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "B2", "value": 100}]})
    assert r.ok and "warning" in r.for_model() and not r.changes and f.current_version == 1


# ---------- Word / PowerPoint ----------

def test_word_create_replace_insert_image(db, chat):
    from app.tools.assets import save_asset
    save_asset(store.assets_dir(chat.id), png_bytes(), "image/png")
    ex = ToolExecutor(db, chat.id, _always, turn_id="t1")
    assert run(ex, "word_create_document", {"file": "bc.docx", "paragraphs": [
        {"text": "Báo cáo", "style": "Heading 1"}, {"text": "Mở đầu"}]}).ok
    assert run(ToolExecutor(db, chat.id, _always, turn_id="t2"), "word_replace_paragraph",
               {"file": "bc.docx", "index": 1, "text": "Mở đầu mới"}).ok
    r = run(ToolExecutor(db, chat.id, _always, turn_id="t3"), "word_insert_image",
            {"file": "bc.docx", "image": "anh-1.png", "after_index": 0, "width_cm": 3})
    assert r.ok and r.changes[0].version == 3
    f = next(x for x in chat.files if x.name == "bc.docx")
    doc = Document(store.working_path(f))
    assert [p.text for p in doc.paragraphs] == ["Báo cáo", "", "Mở đầu mới"] and len(doc.inline_shapes) == 1


def test_pptx_create_text_notes(db, chat):
    ex = ToolExecutor(db, chat.id, _always, turn_id="t1")
    r = run(ex, "pptx_create_presentation", {"file": "sp.pptx", "slides": [
        {"layout": "title", "title": "Sản phẩm"},
        {"title": "Tính năng", "bullets": ["Nhanh", "Rẻ"], "notes": "Nhấn mạnh giá"}]})
    assert r.ok
    out = run(ex, "pptx_inspect", {"file": "sp.pptx"}).data
    assert out["slide_size_cm"] == [33.9, 19.1] and out["slides"][1]["notes"] == "Nhấn mạnh giá"
    r = run(ex, "pptx_set_text", {"file": "sp.pptx", "slide": 1, "shape": 1, "text": "Dòng 1\nDòng 2"})
    assert r.ok and r.changes[0].version == 1  # cùng yêu cầu tạo tệp → gộp vào phiên bản 1
    f = next(x for x in chat.files if x.name == "sp.pptx")
    assert Presentation(store.working_path(f)).slides[1].placeholders[1].text_frame.text == "Dòng 1\nDòng 2"


def test_render_pages_degrades_without_libreoffice(db, chat, monkeypatch):
    from app.preview import render
    monkeypatch.setattr(render, "available", lambda: False)
    store.create_file(db, chat.id, "p.pptx", pptx_bytes())
    r = run(ToolExecutor(db, chat.id, _always), "render_pages", {"file": "p.pptx"})
    assert r.ok and r.data["available"] is False and not r.images


def test_pdf_to_png(tmp_path):
    import pymupdf
    from app.preview.render import pdf_to_pngs
    pdf = tmp_path / "a.pdf"
    with pymupdf.open() as doc:
        for _ in range(2):
            doc.new_page()
        doc.save(pdf)
    pages = pdf_to_pngs(pdf, tmp_path, dpi=20)
    assert [p.name for p in pages] == ["page-0.png", "page-1.png"] and pages[0].read_bytes()[:4] == b"\x89PNG"


def test_write_succeeds_while_preview_is_reading_the_file(db, chat):
    """Windows: giao diện đang tải bản xem trước (giữ handle đọc) không được làm hỏng lần ghi của agent."""
    f = store.create_file(db, chat.id, "busy.xlsx", xlsx_bytes())
    with open(store.working_path(f), "rb"):
        r = run(ToolExecutor(db, chat.id, _always, turn_id="t1"), "excel_write_cells",
                {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "B2", "value": 7}]})
    assert r.ok and r.changes[0].version == 2
    assert ws_of(f)["B2"].value == 7
    assert not list(store.working_path(f).parent.glob(".tmp-*"))

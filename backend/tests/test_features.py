"""Tính năng theo đề xuất: sắp xếp/lọc, kiểm tra công thức, Word nâng cao, PowerPoint nâng cao,
định dạng từ khoá, so sánh, ảnh, OCR, run_python (sandbox)."""
import asyncio
import base64
import json
from pathlib import Path

import httpx
import openpyxl
import pytest
from docx import Document
from docx.oxml.ns import qn
from pptx import Presentation

from app.tools import system
from app.tools.assets import list_assets, save_asset
from app.tools.executor import ToolExecutor
from app.versioning import store

from .conftest import docx_bytes, png_bytes, pptx_bytes, xlsx_bytes


async def _always(_n, _a):
    return True


def run(ex, name, args):
    return asyncio.run(ex.run(name, args))


def ex_for(db, chat, turn="t1"):
    return ToolExecutor(db, chat.id, _always, turn_id=turn)


# ---------- Excel ----------

def test_formula_checked_and_modern_functions_prefixed(db, chat):
    f = store.create_file(db, chat.id, "f.xlsx", xlsx_bytes())
    ex = ex_for(db, chat)
    bad = run(ex, "excel_write_cells", {"file": f.name, "sheet": "Doanh thu", "cells": [
        {"ref": "C2", "value": "=FOO(B2)"}, {"ref": "C3", "value": "=SUM(Khong!A1:A2)"}]})
    assert not bad.ok and "#NAME?" in bad.data["error"] and "#REF!" in bad.data["error"]
    ok = run(ex, "excel_write_cells", {"file": f.name, "sheet": "Doanh thu",
                                       "cells": [{"ref": "C2", "value": "=XLOOKUP(2,A:A,B:B)"}]})
    assert ok.ok
    assert openpyxl.load_workbook(store.working_path(f))["Doanh thu"]["C2"].value == "=_xlfn.XLOOKUP(2,A:A,B:B)"


def test_sort_and_filter(db, chat):
    f = store.create_file(db, chat.id, "s.xlsx", xlsx_bytes())
    ex = ex_for(db, chat)
    r = run(ex, "excel_sort_range", {"file": f.name, "sheet": "Doanh thu", "range": "A2:B4", "by_column": "B",
                                     "descending": True})
    assert r.ok
    ws = openpyxl.load_workbook(store.working_path(f))["Doanh thu"]
    assert [ws[f"B{i}"].value for i in (2, 3, 4)] == [150, 120, 100] and ws["A2"].value == 2
    r = run(ex, "excel_set_filter", {"file": f.name, "sheet": "Doanh thu", "range": "A1:B4"})
    assert r.ok and r.changes[0].diff["filters"][0]["after"] == "A1:B4"


def test_chart_with_error_bars_and_inspect_reports_it(db, chat):
    f = store.create_file(db, chat.id, "e.xlsx", xlsx_bytes())
    ex = ex_for(db, chat)
    run(ex, "excel_write_cells", {"file": f.name, "sheet": "Doanh thu",
                                  "cells": [{"ref": f"C{i}", "value": 5} for i in (2, 3, 4)]})
    r = run(ex, "excel_add_chart", {"file": f.name, "sheet": "Doanh thu", "chart_type": "column",
                                    "data_range": "B1:B4", "categories_range": "A2:A4", "error_range": "C2:C4",
                                    "title": "DT"})
    assert r.ok
    charts = run(ex, "excel_inspect", {"file": f.name}).data["sheets"][0]["charts"]
    assert charts[0]["type"] == "column" and charts[0]["title"] == "DT"
    assert charts[0]["series"][0]["values"].endswith("$B$2:$B$4") or "B2:B4" in charts[0]["series"][0]["values"]


# ---------- Word ----------

def test_word_table_find_replace_rewrite(db, chat):
    f = store.create_file(db, chat.id, "w.docx", docx_bytes())
    ex = ex_for(db, chat)
    assert run(ex, "word_insert_table", {"file": f.name, "after_index": 0, "rows": [["A", "B"], ["1", "2"]]}).ok
    r = run(ex, "word_find_replace", {"file": f.name, "items": [{"find": "đoạn", "replace": "mục"}]})
    assert r.data["replaced"]["đoạn"] == 2
    assert run(ex, "word_rewrite_paragraphs", {"file": f.name, "items": [{"index": 0, "text": "Report"}]}).ok
    doc = Document(store.working_path(f))
    assert [p.text for p in doc.paragraphs] == ["Report", "mục một.", "mục hai."]
    assert doc.tables[0].cell(1, 1).text == "2"
    assert doc.element.body.index(doc.tables[0]._tbl) == 1  # bảng nằm ngay sau đoạn 0


def test_word_comment_and_track_changes(db, chat):
    f = store.create_file(db, chat.id, "rv.docx", docx_bytes())
    ex = ex_for(db, chat)
    r = run(ex, "word_add_comment", {"file": f.name, "items": [{"index": 1, "comment": "Cần số liệu"}]})
    assert r.ok and r.changes
    r = run(ex, "word_suggest_edit", {"file": f.name, "items": [{"index": 2, "text": "Đoạn hai đã sửa."}]})
    assert r.ok and r.changes
    doc = Document(store.working_path(f))
    assert any(c.text == "Cần số liệu" for c in doc.comments)
    p = doc.paragraphs[2]._p
    assert p.find(qn("w:del")) is not None and p.find(qn("w:ins")) is not None
    assert "Đoạn hai đã sửa." in "".join(t.text for t in p.iter(qn("w:t")))


# ---------- PowerPoint ----------

def test_pptx_theme_add_move_delete_table_chart(db, chat):
    ex = ex_for(db, chat)
    assert run(ex, "pptx_create_presentation", {"file": "t.pptx", "theme": "midnight", "slides": [
        {"layout": "title", "title": "Mở đầu"}, {"title": "Hai", "bullets": ["x"]}]}).ok
    assert run(ex, "pptx_add_slide", {"file": "t.pptx", "after": -1, "slide": {"title": "Đầu tiên"}}).ok
    assert run(ex, "pptx_move_slide", {"file": "t.pptx", "slide": 0, "to": 2}).ok
    assert run(ex, "pptx_add_table", {"file": "t.pptx", "slide": 0, "rows": [["Q", "DT"], ["1", "10"]]}).ok
    assert run(ex, "pptx_add_chart", {"file": "t.pptx", "slide": 1, "chart_type": "column",
                                      "categories": ["Q1", "Q2"], "series": {"DT": [10, 12]}}).ok
    assert "không cùng số" in run(ex, "pptx_add_chart", {"file": "t.pptx", "slide": 1, "chart_type": "line",
                                  "categories": ["Q1"], "series": {"DT": [1, 2]}}).data["error"]
    assert run(ex, "pptx_delete_slide", {"file": "t.pptx", "slide": 2}).ok
    f = next(x for x in chat.files if x.name == "t.pptx")
    prs = Presentation(store.working_path(f))
    titles = [s.shapes.title.text for s in prs.slides]
    assert titles == ["Mở đầu", "Hai"]
    assert any(sh.has_table for sh in prs.slides[0].shapes) and any(sh.has_chart for sh in prs.slides[1].shapes)
    assert str(prs.slides[0].background.fill.fore_color.rgb) == "0F1923"


# ---------- Định dạng từ khoá ----------

@pytest.mark.parametrize("name,data", [("k.docx", docx_bytes), ("k.pptx", pptx_bytes), ("k.xlsx", xlsx_bytes)])
def test_format_keywords_all_formats(db, chat, name, data):
    f = store.create_file(db, chat.id, name, data())
    kw = {"k.docx": "hai", "k.pptx": "dung", "k.xlsx": "thu"}[name]
    r = run(ex_for(db, chat), "format_keywords", {"file": f.name, "keywords": [kw], "color": "C00000", "bold": True})
    assert r.ok and r.data["matches"] >= 1 and r.changes, r.data


def test_format_keywords_reports_missing(db, chat):
    f = store.create_file(db, chat.id, "m.docx", docx_bytes())
    r = run(ex_for(db, chat), "format_keywords", {"file": f.name, "keywords": ["khôngcó"], "bold": True})
    assert not r.ok and "Không tìm thấy" in r.data["error"]


def test_rich_text_survives_other_excel_edits(db, chat):
    f = store.create_file(db, chat.id, "rt.xlsx", xlsx_bytes())
    ex = ex_for(db, chat)
    run(ex, "format_keywords", {"file": f.name, "keywords": ["thu"], "color": "C00000"})
    run(ex, "excel_write_cells", {"file": f.name, "sheet": "Doanh thu", "cells": [{"ref": "D1", "value": "x"}]})
    wb = openpyxl.load_workbook(store.working_path(f), rich_text=True)
    assert type(wb["Doanh thu"]["B1"].value).__name__ == "CellRichText"


# ---------- So sánh, ảnh, OCR ----------

def test_compare_versions_and_files(db, chat):
    a = store.create_file(db, chat.id, "a.xlsx", xlsx_bytes())
    store.create_file(db, chat.id, "b.xlsx", xlsx_bytes())
    run(ex_for(db, chat), "excel_write_cells", {"file": a.name, "sheet": "Doanh thu",
                                                "cells": [{"ref": "B2", "value": 1}]})
    r = run(ex_for(db, chat, "t2"), "compare_versions", {"file": "a.xlsx", "from_version": 1})
    assert r.ok and r.data["diff"]["cells"][0]["ref"] == "B2"
    r = run(ex_for(db, chat, "t2"), "compare_files", {"file": "b.xlsx", "other": "a.xlsx"})
    assert r.ok and "1 ô đổi giá trị" in r.data["summary"]


def test_image_edit_creates_new_asset(db, chat):
    save_asset(store.assets_dir(chat.id), png_bytes(), "image/png")
    r = run(ex_for(db, chat), "image_edit", {"image": "anh-1.png", "rotate": 90, "crop": [0, 0, 0.5, 1]})
    assert r.ok and r.data["created_image"] == "anh-2.jpg" and r.data["size"] == [10, 40]
    assert list_assets(store.assets_dir(chat.id)) == ["anh-1.png", "anh-2.jpg"]


def test_ocr_unavailable_and_cer():
    from app.media.ocr import cer, table_cell_accuracy
    assert cer("Hóa đơn 100", "Hóa đơn 100") == 0 and round(cer("abcd", "abed"), 2) == 0.25
    assert table_cell_accuracy([["a", "1"], ["b", "2"]], [["a", "1"], ["b", "3"]]) == 0.75


# ---------- run_python + sandbox ----------



def test_sandbox_runner_collects_outputs():
    import importlib.util
    spec = importlib.util.spec_from_file_location("sandbox_app", Path(__file__).resolve().parents[2] / "sandbox" / "app.py")
    sb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sb)
    res = sb.run(sb.RunRequest(code="open('kq.csv','w').write('a,b\\n1,2\\n')\nprint(open('in.txt').read())",
                               files={"in.txt": base64.b64encode(b"xin chao").decode()}, timeout=20))
    assert res.exit_code == 0 and "xin chao" in res.stdout and list(res.outputs) == ["kq.csv"]
    slow = sb.run(sb.RunRequest(code="import time; time.sleep(5)", timeout=1))
    assert slow.timed_out


def test_run_python_tool_via_sandbox(db, chat, monkeypatch):
    from app.config import get_settings
    store.create_file(db, chat.id, "data.xlsx", xlsx_bytes())
    seen = {}

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        seen.update(body)
        return httpx.Response(200, json={"exit_code": 0, "stdout": "R2=0.91", "stderr": "", "timed_out": False,
                                         "outputs": {"hinh.png": base64.b64encode(png_bytes()).decode(),
                                                     "bang.csv": base64.b64encode(b"x,y\n1,2").decode(),
                                                     "kq.xlsx": base64.b64encode(xlsx_bytes()).decode()}})
    monkeypatch.setattr(get_settings(), "sandbox_url", "http://sandbox")
    monkeypatch.setattr(system, "_transport", httpx.MockTransport(handler))
    r = run(ex_for(db, chat), "run_python", {"code": "print(1)", "files": ["data.xlsx"]})
    assert r.ok and r.data["stdout"] == "R2=0.91" and "data.xlsx" in seen["files"]
    assert [o.get("saved_as_image") or o.get("saved_as") or o.get("content") for o in r.data["outputs"]] == \
           ["x,y\n1,2", "anh-1.png", "kq.xlsx"] or len(r.data["outputs"]) == 3
    assert len(r.images) == 1 and r.changes[0].file_name == "kq.xlsx"


def test_run_python_disabled_without_sandbox(db, chat):
    r = run(ex_for(db, chat), "run_python", {"code": "print(1)"})
    assert not r.ok and "SANDBOX_URL" in r.data["error"]


def test_run_python_needs_confirmation(db, chat):
    async def never(_n, _a):
        return False
    r = asyncio.run(ToolExecutor(db, chat.id, never).run("run_python", {"code": "print(1)"}))
    assert not r.ok and "từ chối" in r.data["error"]


def test_review_flow_suggest_then_comment_same_paragraph(db, chat):
    """Hồi quy từ bộ đánh giá Gemini: nhận xét vào đoạn vừa đề xuất sửa từng lỗi "Đoạn trống",
    và word_inspect hiện đoạn đó rỗng khiến agent tưởng đoạn bị xoá."""
    f = store.create_file(db, chat.id, "hd.docx", docx_bytes())
    ex = ex_for(db, chat)
    r = run(ex, "word_suggest_edit", {"file": f.name, "items": [{"index": 1, "text": "Mục một rõ hơn."},
                                                                 {"index": 2, "text": "Mục hai rõ hơn."}]})
    assert r.ok and r.data["suggested"] == [1, 2]
    r = run(ex, "word_add_comment", {"file": f.name, "items": [{"index": 1, "comment": "Thiếu thời hạn"},
                                                                {"index": 2, "comment": "Nêu rõ bên nào"}]})
    assert r.ok, r.data
    paras = run(ex, "word_inspect", {"file": f.name}).data["paragraphs"]
    assert paras[1]["text"] == "Mục một rõ hơn."
    assert paras[1]["pending_suggestion"] == {"old": "Đoạn một.", "new": "Mục một rõ hơn."}
    again = run(ex, "word_suggest_edit", {"file": f.name, "items": [{"index": 1, "text": "Lần hai"}]})
    assert not again.ok and "chờ duyệt" in again.data["error"]
    doc = Document(store.working_path(f))
    assert sorted(c.text for c in doc.comments) == ["Nêu rõ bên nào", "Thiếu thời hạn"]


def test_pptx_set_text_many_items_one_call(db, chat):
    ex = ex_for(db, chat)
    run(ex, "pptx_create_presentation", {"file": "m.pptx", "slides": [
        {"title": "A", "bullets": ["a"]}, {"title": "B", "bullets": ["b"]}]})
    r = run(ex, "pptx_set_text", {"file": "m.pptx", "items": [
        {"slide": 0, "shape": 0, "text": "Mở đầu"}, {"slide": 1, "shape": 1, "text": "Ý 1\nÝ 2"}]})
    assert r.ok and r.data["updated"] == [[0, 0], [1, 1]]
    f = next(x for x in chat.files if x.name == "m.pptx")
    prs = Presentation(store.working_path(f))
    assert prs.slides[0].shapes.title.text == "Mở đầu"
    assert prs.slides[1].placeholders[1].text_frame.text == "Ý 1\nÝ 2"

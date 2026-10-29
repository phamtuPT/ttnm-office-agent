"""So sánh hai phiên bản tệp: hiển thị thay đổi cho người dùng và phát hiện agent "nói đã sửa" mà tệp không đổi."""
import difflib
from pathlib import Path

import openpyxl
from openpyxl.cell.rich_text import CellRichText
from docx import Document
from pptx import Presentation

MAX_ITEMS = 200


def compute(kind: str, before: Path, after: Path) -> dict:
    return {"xlsx": _xlsx, "docx": _docx, "pptx": _pptx}[kind](before, after)


def is_empty(diff: dict) -> bool:
    keys = ("cells", "paragraphs", "slides", "sheets_added", "sheets_removed", "charts", "conditional", "filters", "tables",
            "created", "styles", "design")
    return not any(diff.get(k) for k in keys)


def summarize(diff: dict) -> str:
    if diff.get("created"):
        return "Tạo tệp mới"
    parts = []
    cells = diff.get("cells") or []
    n_val = sum(1 for c in cells if c.get("kind") != "format")
    n_fmt = len(cells) - n_val
    if n_val:
        parts.append(f"{diff.get('values_total', n_val)} ô đổi giá trị")
    if n_fmt:
        parts.append(f"{diff.get('formats_total', n_fmt)} ô đổi định dạng")
    if diff.get("sheets_added"):
        parts.append("thêm sheet " + ", ".join(diff["sheets_added"]))
    if diff.get("sheets_removed"):
        parts.append("xoá sheet " + ", ".join(diff["sheets_removed"]))
    for c in diff.get("charts") or []:
        parts.append(f"biểu đồ sheet {c['sheet']}: {c['before']} → {c['after']}")
    for c in diff.get("conditional") or []:
        parts.append(f"định dạng có điều kiện sheet {c['sheet']}: {c['before']} → {c['after']} quy tắc")
    for c in diff.get("filters") or []:
        parts.append(f"bộ lọc sheet {c['sheet']}: {c['after'] or 'đã bỏ'}")
    if diff.get("paragraphs"):
        parts.append(f"{sum(max(len(p['before']), len(p['after'])) for p in diff['paragraphs'])} đoạn văn thay đổi")
    if diff.get("tables"):
        t = diff["tables"]
        parts.append(f"số bảng {t['before']} → {t['after']}" if t["before"] != t["after"] else "nội dung bảng thay đổi")
    if diff.get("slides"):
        parts.append(f"{len(diff['slides'])} slide thay đổi")
    if diff.get("styles"):
        parts.append("đổi kiểu chữ (styles) của tài liệu")
    if diff.get("design"):
        parts.append("đổi thiết kế/bảng màu")
    return "; ".join(parts) or "Không có thay đổi"


# ---------- Excel ----------

def _style(cell) -> tuple:
    f = cell.font
    fill = cell.fill.fgColor.rgb if cell.fill and cell.fill.fill_type else None
    return (cell.number_format, bool(f.b), bool(f.i), bool(f.u), f.color.rgb if f.color else None,
            f.sz, fill)


def _cf_rules(ws) -> list[str]:
    return sorted(f"{cf.sqref}:{r.type}:{r.operator}:{r.formula}" for cf in ws.conditional_formatting for r in cf.rules)


def _xlsx(before: Path, after: Path) -> dict:
    wb_a, wb_b = openpyxl.load_workbook(before, rich_text=True), openpyxl.load_workbook(after, rich_text=True)
    names_a, names_b = set(wb_a.sheetnames), set(wb_b.sheetnames)
    cells, n_val, n_fmt, charts, conditional, filters = [], 0, 0, [], [], []
    for name in wb_b.sheetnames:
        if name not in names_a:
            continue
        ws_a, ws_b = wb_a[name], wb_b[name]
        if len(ws_a._charts) != len(ws_b._charts):
            charts.append({"sheet": name, "before": len(ws_a._charts), "after": len(ws_b._charts)})
        if ws_a.auto_filter.ref != ws_b.auto_filter.ref:
            filters.append({"sheet": name, "before": ws_a.auto_filter.ref, "after": ws_b.auto_filter.ref})
        cf_a, cf_b = _cf_rules(ws_a), _cf_rules(ws_b)
        if cf_a != cf_b:
            conditional.append({"sheet": name, "before": len(cf_a), "after": len(cf_b)})
        for r in range(1, max(ws_a.max_row, ws_b.max_row) + 1):
            for c in range(1, max(ws_a.max_column, ws_b.max_column) + 1):
                ca, cb = ws_a.cell(r, c), ws_b.cell(r, c)
                if _plain(ca.value) != _plain(cb.value):
                    n_val += 1
                    item = {"sheet": name, "ref": cb.coordinate, "kind": "value",
                            "before": _jsonable(ca.value), "after": _jsonable(cb.value)}
                elif _style(ca) != _style(cb) or repr(ca.value) != repr(cb.value):  # gồm rich text
                    n_fmt += 1
                    item = {"sheet": name, "ref": cb.coordinate, "kind": "format",
                            "before": _jsonable(ca.value), "after": _jsonable(cb.value)}
                else:
                    continue
                if len(cells) < MAX_ITEMS:
                    cells.append(item)
    return {"cells": cells, "values_total": n_val, "formats_total": n_fmt, "charts": charts, "conditional": conditional, "filters": filters,
            "sheets_added": sorted(names_b - names_a), "sheets_removed": sorted(names_a - names_b)}


# ---------- Word ----------

def _para_key(p) -> str:
    # Cả XML của đoạn: phát hiện đổi định dạng, comment, Track Changes, ảnh — không chỉ chữ
    return f"{p.style.name}\x00{p._p.xml}"


def _docx(before: Path, after: Path) -> dict:
    from ..tools.word import para_markup  # import muộn: tránh vòng import tools ↔ versioning

    da, db = Document(before), Document(after)
    pa, pb = da.paragraphs, db.paragraphs
    ka, kb = [_para_key(p) for p in pa], [_para_key(p) for p in pb]
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ka, b=kb, autojunk=False).get_opcodes():
        if tag != "equal":
            ops.append({"op": tag, "before_index": i1, "after_index": j1,
                        "before": [para_markup(p) for p in pa[i1:i2]], "after": [para_markup(p) for p in pb[j1:j2]]})
    out = {"paragraphs": ops[:MAX_ITEMS]}
    if [t._tbl.xml for t in da.tables] != [t._tbl.xml for t in db.tables]:
        out["tables"] = {"before": len(da.tables), "after": len(db.tables)}
    # Kiểu chữ dùng chung (Heading, Normal...) và lề trang: đổi được mà không đoạn nào khác XML
    if da.styles.element.xml != db.styles.element.xml or             [s._sectPr.xml for s in da.sections] != [s._sectPr.xml for s in db.sections]:
        out["styles"] = True
    return out


# ---------- PowerPoint ----------

def _slide_sig(s) -> str:
    # XML các shape: chữ, định dạng run, vị trí, bảng, biểu đồ; cộng nền và ghi chú
    from ..tools.pptx_math import all_shapes
    shapes = [sh._element.xml for sh in all_shapes(s)]
    notes = s.notes_slide.notes_text_frame.text if s.has_notes_slide else ""
    return repr((shapes, s.background._cSld.xml if hasattr(s.background, "_cSld") else "", notes))


def _slide_text(s) -> str:
    from ..tools.pptx_math import all_shapes, shape_markup
    return "\n".join(shape_markup(sh) for sh in all_shapes(s) if sh.has_text_frame)


def _design_sig(prs) -> tuple:
    """Theme (bảng màu, phông) + master + layout: đổi mẫu thiết kế không làm khác XML của slide nào."""
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    master = prs.slide_master
    return (master.part.part_related_by(RT.THEME).blob, master._element.xml,
            tuple(layout._element.xml for layout in prs.slide_layouts))


def _pptx(before: Path, after: Path) -> dict:
    pa, pb = Presentation(before), Presentation(after)
    sa, sb = list(pa.slides), list(pb.slides)
    slides = []
    for i in range(max(len(sa), len(sb))):
        a = sa[i] if i < len(sa) else None
        b = sb[i] if i < len(sb) else None
        if (a is None) != (b is None) or (a is not None and _slide_sig(a) != _slide_sig(b)):
            slides.append({"index": i, "before": _slide_text(a) if a is not None else None,
                           "after": _slide_text(b) if b is not None else None})
    out = {"slides": slides[:MAX_ITEMS]}
    if _design_sig(pa) != _design_sig(pb):
        out["design"] = True
    return out


def _plain(v):
    return str(v) if isinstance(v, CellRichText) else v


def _jsonable(v):
    return v if v is None or isinstance(v, (int, float, str, bool)) else str(v)

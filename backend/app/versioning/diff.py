"""So sánh hai phiên bản tệp: hiển thị thay đổi cho người dùng và phát hiện agent "nói đã sửa" mà tệp không đổi."""
import difflib
from pathlib import Path

import openpyxl
from docx import Document
from pptx import Presentation

MAX_ITEMS = 200


def compute(kind: str, before: Path, after: Path) -> dict:
    return {"xlsx": _xlsx, "docx": _docx, "pptx": _pptx}[kind](before, after)


def is_empty(diff: dict) -> bool:
    keys = ("cells", "paragraphs", "slides", "sheets_added", "sheets_removed", "charts", "conditional", "tables",
            "created")
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
    if diff.get("paragraphs"):
        parts.append(f"{sum(max(len(p['before']), len(p['after'])) for p in diff['paragraphs'])} đoạn văn thay đổi")
    if diff.get("tables"):
        parts.append(f"số bảng {diff['tables']['before']} → {diff['tables']['after']}")
    if diff.get("slides"):
        parts.append(f"{len(diff['slides'])} slide thay đổi")
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
    wb_a, wb_b = openpyxl.load_workbook(before), openpyxl.load_workbook(after)
    names_a, names_b = set(wb_a.sheetnames), set(wb_b.sheetnames)
    cells, n_val, n_fmt, charts, conditional = [], 0, 0, [], []
    for name in wb_b.sheetnames:
        if name not in names_a:
            continue
        ws_a, ws_b = wb_a[name], wb_b[name]
        if len(ws_a._charts) != len(ws_b._charts):
            charts.append({"sheet": name, "before": len(ws_a._charts), "after": len(ws_b._charts)})
        cf_a, cf_b = _cf_rules(ws_a), _cf_rules(ws_b)
        if cf_a != cf_b:
            conditional.append({"sheet": name, "before": len(cf_a), "after": len(cf_b)})
        for r in range(1, max(ws_a.max_row, ws_b.max_row) + 1):
            for c in range(1, max(ws_a.max_column, ws_b.max_column) + 1):
                ca, cb = ws_a.cell(r, c), ws_b.cell(r, c)
                if ca.value != cb.value:
                    n_val += 1
                    item = {"sheet": name, "ref": cb.coordinate, "kind": "value",
                            "before": _jsonable(ca.value), "after": _jsonable(cb.value)}
                elif _style(ca) != _style(cb):
                    n_fmt += 1
                    item = {"sheet": name, "ref": cb.coordinate, "kind": "format",
                            "before": _jsonable(ca.value), "after": _jsonable(cb.value)}
                else:
                    continue
                if len(cells) < MAX_ITEMS:
                    cells.append(item)
    return {"cells": cells, "values_total": n_val, "formats_total": n_fmt, "charts": charts, "conditional": conditional,
            "sheets_added": sorted(names_b - names_a), "sheets_removed": sorted(names_a - names_b)}


# ---------- Word ----------

def _para_key(p) -> str:
    # Gồm style + định dạng run để phát hiện cả thay đổi định dạng (in đậm, tô màu từ khoá...)
    runs = "|".join(f"{int(bool(r.bold))}{int(bool(r.italic))}{int(bool(r.underline))}"
                    f"{r.font.color.rgb if r.font.color and r.font.color.type else ''}{r.text}" for r in p.runs)
    return f"{p.style.name}\x00{runs}"


def _docx(before: Path, after: Path) -> dict:
    da, db = Document(before), Document(after)
    pa, pb = da.paragraphs, db.paragraphs
    ka, kb = [_para_key(p) for p in pa], [_para_key(p) for p in pb]
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ka, b=kb, autojunk=False).get_opcodes():
        if tag != "equal":
            ops.append({"op": tag, "before_index": i1, "after_index": j1,
                        "before": [p.text for p in pa[i1:i2]], "after": [p.text for p in pb[j1:j2]]})
    out = {"paragraphs": ops[:MAX_ITEMS]}
    if len(da.tables) != len(db.tables):
        out["tables"] = {"before": len(da.tables), "after": len(db.tables)}
    return out


# ---------- PowerPoint ----------

def _slide_sig(s) -> str:
    texts = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame]
    notes = s.notes_slide.notes_text_frame.text if s.has_notes_slide else ""
    geo = [(sh.shape_type, sh.left, sh.top, sh.width, sh.height) for sh in s.shapes]
    return repr((texts, notes, geo))


def _slide_text(s) -> str:
    return "\n".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)


def _pptx(before: Path, after: Path) -> dict:
    sa, sb = list(Presentation(before).slides), list(Presentation(after).slides)
    slides = []
    for i in range(max(len(sa), len(sb))):
        a = sa[i] if i < len(sa) else None
        b = sb[i] if i < len(sb) else None
        if (a is None) != (b is None) or (a is not None and _slide_sig(a) != _slide_sig(b)):
            slides.append({"index": i, "before": _slide_text(a) if a is not None else None,
                           "after": _slide_text(b) if b is not None else None})
    return {"slides": slides[:MAX_ITEMS]}


def _jsonable(v):
    return v if v is None or isinstance(v, (int, float, str, bool)) else str(v)

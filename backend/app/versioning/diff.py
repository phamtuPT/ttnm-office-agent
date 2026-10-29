"""So sánh hai phiên bản tệp để hiển thị thay đổi và kiểm tra agent có thật sự sửa gì không."""
import difflib
from pathlib import Path

import openpyxl
from docx import Document
from pptx import Presentation

MAX_ITEMS = 200


def compute(kind: str, before: Path, after: Path) -> dict:
    return {"xlsx": _xlsx, "docx": _docx, "pptx": _pptx}[kind](before, after)


def is_empty(diff: dict) -> bool:
    return not any(diff.get(k) for k in ("cells", "paragraphs", "slides", "sheets_added", "sheets_removed"))


def summarize(diff: dict) -> str:
    parts = []
    if diff.get("cells"):
        parts.append(f"{diff.get('cells_total', len(diff['cells']))} ô thay đổi")
    if diff.get("sheets_added"):
        parts.append("thêm sheet " + ", ".join(diff["sheets_added"]))
    if diff.get("sheets_removed"):
        parts.append("xoá sheet " + ", ".join(diff["sheets_removed"]))
    if diff.get("paragraphs"):
        parts.append(f"{len(diff['paragraphs'])} đoạn văn thay đổi")
    if diff.get("slides"):
        parts.append(f"{len(diff['slides'])} slide thay đổi")
    return "; ".join(parts) or "Không có thay đổi"


def _xlsx(before: Path, after: Path) -> dict:
    wb_a, wb_b = openpyxl.load_workbook(before), openpyxl.load_workbook(after)
    names_a, names_b = set(wb_a.sheetnames), set(wb_b.sheetnames)
    cells, total = [], 0
    for name in wb_b.sheetnames:
        if name not in names_a:
            continue
        ws_a, ws_b = wb_a[name], wb_b[name]
        max_r = max(ws_a.max_row, ws_b.max_row)
        max_c = max(ws_a.max_column, ws_b.max_column)
        for r in range(1, max_r + 1):
            for c in range(1, max_c + 1):
                va, vb = ws_a.cell(r, c).value, ws_b.cell(r, c).value
                if va != vb:
                    total += 1
                    if len(cells) < MAX_ITEMS:
                        cells.append({"sheet": name, "ref": ws_b.cell(r, c).coordinate,
                                      "before": _jsonable(va), "after": _jsonable(vb)})
    return {"cells": cells, "cells_total": total,
            "sheets_added": sorted(names_b - names_a), "sheets_removed": sorted(names_a - names_b)}


def _docx(before: Path, after: Path) -> dict:
    pa = [p.text for p in Document(before).paragraphs]
    pb = [p.text for p in Document(after).paragraphs]
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=pa, b=pb, autojunk=False).get_opcodes():
        if tag != "equal":
            ops.append({"op": tag, "before_index": i1, "after_index": j1,
                        "before": pa[i1:i2], "after": pb[j1:j2]})
    return {"paragraphs": ops[:MAX_ITEMS]}


def _slide_texts(path: Path) -> list[str]:
    return ["\n".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            for s in Presentation(path).slides]


def _pptx(before: Path, after: Path) -> dict:
    sa, sb = _slide_texts(before), _slide_texts(after)
    slides = []
    for i in range(max(len(sa), len(sb))):
        a = sa[i] if i < len(sa) else None
        b = sb[i] if i < len(sb) else None
        if a != b:
            slides.append({"index": i, "before": a, "after": b})
    return {"slides": slides[:MAX_ITEMS]}


def _jsonable(v):
    return v if v is None or isinstance(v, (int, float, str, bool)) else str(v)

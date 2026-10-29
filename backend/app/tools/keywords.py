"""Định dạng từ khoá: tô màu / in đậm / gạch chân / đổi cỡ đúng chuỗi ký tự cần nhấn mạnh, trên cả ba định dạng."""
import copy
import re

import openpyxl
from docx import Document
from docx.shared import Pt as DocxPt
from docx.shared import RGBColor as DocxRGB
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from pptx import Presentation
from pptx.dml.color import RGBColor as PptxRGB
from pptx.util import Pt as PptxPt
from pydantic import BaseModel, Field

from .registry import ToolCtx, ToolError, tool


class KeywordArgs(BaseModel):
    file: str = Field(description="Tên tệp .docx, .pptx hoặc .xlsx")
    keywords: list[str] = Field(description="Các chuỗi cần nhấn mạnh (khớp đúng chữ, không phân biệt hoa thường)")
    color: str | None = Field(None, description="Màu chữ hex RRGGBB, ví dụ C00000")
    bold: bool | None = None
    underline: bool | None = None
    size_pt: float | None = None


def _pattern(keywords: list[str]) -> re.Pattern:
    words = sorted({k for k in keywords if k.strip()}, key=len, reverse=True)
    if not words:
        raise ToolError("Cần ít nhất một từ khoá")
    return re.compile("|".join(re.escape(w) for w in words), re.I)


def _split_run(run, pattern, style_fn, new_run) -> int:
    """Tách một run thành các run nhỏ, áp định dạng cho phần khớp. Trả về số lần khớp."""
    text = run.text
    pieces, last = [], 0
    for m in pattern.finditer(text):
        pieces += [(text[last:m.start()], False), (m.group(0), True)]
        last = m.end()
    if not pieces:
        return 0
    pieces.append((text[last:], False))
    pieces = [p for p in pieces if p[0]]
    run.text = pieces[0][0]
    if pieces[0][1]:
        style_fn(run)
    anchor = run
    for txt, hit in pieces[1:]:
        r = new_run(anchor, txt)
        if hit:
            style_fn(r)
        anchor = r
    return sum(1 for _, hit in pieces if hit)


def _docx(args: KeywordArgs, ctx: ToolCtx, pattern) -> int:
    from docx.text.run import Run

    doc = Document(ctx.path)

    def style(r):
        if args.color:
            r.font.color.rgb = DocxRGB.from_string(args.color.lstrip("#"))
        if args.bold is not None:
            r.bold = args.bold
        if args.underline is not None:
            r.underline = args.underline
        if args.size_pt:
            r.font.size = DocxPt(args.size_pt)

    def new_run(anchor, txt):
        el = copy.deepcopy(anchor._r)
        anchor._r.addnext(el)
        r = Run(el, anchor._parent)
        r.text = txt
        return r

    paras = list(doc.paragraphs) + [p for t in doc.tables for row in t.rows for c in row.cells for p in c.paragraphs]
    if ctx.selection and ctx.selection.paragraphs is not None:
        paras = [p for i, p in enumerate(doc.paragraphs) if i in ctx.selection.paragraphs]
    n = sum(_split_run(r, pattern, style, new_run) for p in paras for r in list(p.runs))
    doc.save(ctx.path)
    return n


def _pptx(args: KeywordArgs, ctx: ToolCtx, pattern) -> int:
    prs = Presentation(ctx.path)

    def style(r):
        if args.color:
            r.font.color.rgb = PptxRGB.from_string(args.color.lstrip("#"))
        if args.bold is not None:
            r.font.bold = args.bold
        if args.underline is not None:
            r.font.underline = args.underline
        if args.size_pt:
            r.font.size = PptxPt(args.size_pt)

    def new_run(anchor, txt):
        el = copy.deepcopy(anchor._r)
        anchor._r.addnext(el)
        from pptx.text.text import _Run
        r = _Run(el, anchor._parent)
        r.text = txt
        return r

    n = 0
    for i, s in enumerate(prs.slides):
        if ctx.selection and ctx.selection.slides is not None and i not in ctx.selection.slides:
            continue
        for sh in s.shapes:
            if sh.has_text_frame:
                n += sum(_split_run(r, pattern, style, new_run) for p in sh.text_frame.paragraphs for r in list(p.runs))
    prs.save(ctx.path)
    return n


def _xlsx(args: KeywordArgs, ctx: ToolCtx, pattern) -> int:
    wb = openpyxl.load_workbook(ctx.path, rich_text=True)
    font = InlineFont(color=args.color.lstrip("#") if args.color else None, b=args.bold,
                      u="single" if args.underline else None, sz=args.size_pt)
    n = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if not isinstance(c.value, str) or c.value.startswith("=") or not pattern.search(c.value):
                    continue
                text, parts, last = c.value, [], 0
                for m in pattern.finditer(text):
                    if m.start() > last:
                        parts.append(text[last:m.start()])
                    parts.append(TextBlock(font, m.group(0)))
                    last = m.end()
                    n += 1
                if last < len(text):
                    parts.append(text[last:])
                c.value = CellRichText(*parts)
    wb.save(ctx.path)
    return n


@tool("format_keywords", "Nhấn mạnh từ khoá: tô màu, in đậm, gạch chân hoặc đổi cỡ ĐÚNG chuỗi ký tự cần nhấn mạnh "
      "(không cả đoạn/cả ô), dùng được cho Word, PowerPoint, Excel.", KeywordArgs, writes=True)
def format_keywords(args: KeywordArgs, ctx: ToolCtx) -> dict:
    if not any([args.color, args.bold is not None, args.underline is not None, args.size_pt]):
        raise ToolError("Cần ít nhất một kiểu định dạng: color, bold, underline hoặc size_pt")
    pattern = _pattern(args.keywords)
    kind = ctx.path.suffix.lower().lstrip(".")
    n = {"docx": _docx, "pptx": _pptx, "xlsx": _xlsx}[kind](args, ctx, pattern)
    if n == 0:
        raise ToolError(f"Không tìm thấy từ khoá nào trong tệp: {args.keywords}")
    return {"matches": n}

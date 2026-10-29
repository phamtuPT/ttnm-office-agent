"""Ảnh thu nhỏ của tệp cho thẻ "Phiên làm việc gần đây" (giống ảnh thu nhỏ của Google Sheets/Docs/Slides).

- Có LibreOffice: chụp đúng trang/slide đầu tiên (render.py) rồi thu nhỏ.
- Không có: tự vẽ bằng Pillow từ nội dung thật — lưới ô kèm giá trị (Excel), trang chữ có đề mục (Word),
  slide đầu với nền, tiêu đề và gạch đầu dòng (PowerPoint).
Ảnh được cache theo phiên bản tệp nên chỉ vẽ lại khi tệp đổi.
"""
import io
import unicodedata
from functools import lru_cache
from pathlib import Path

import openpyxl
from docx import Document
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation

from . import render

W, H = 480, 300
PAGE = (255, 255, 255)
INK = (32, 33, 36)
MUTED = (95, 99, 104)
GRID = (218, 220, 224)
HEAD = (241, 243, 244)

_FONT_CANDIDATES = {
    False: ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf"],
    True: ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
           "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
           "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
}


@lru_cache(maxsize=32)
def _font(size: int, bold: bool = False):
    for path in _FONT_CANDIDATES[bold]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _t(v) -> str:
    return unicodedata.normalize("NFC", "" if v is None else str(v))


def _fit(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…" if text else ""


def _wrap(draw, text: str, font, width: int, max_lines: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return [_fit(draw, ln, font, width) for ln in lines[:max_lines]]


def _xlsx(path: Path) -> Image.Image:
    img = Image.new("RGB", (W, H), PAGE)
    d = ImageDraw.Draw(img)
    ws = openpyxl.load_workbook(path, read_only=True, data_only=False).worksheets[0]
    rows = [[_t(v) for v in r] for r in ws.iter_rows(min_row=1, max_row=22, max_col=10, values_only=True)]
    ncols = max([len(r) for r in rows] + [6])
    widths = []
    small, bold = _font(10), _font(10, True)
    for c in range(min(ncols, 10)):
        longest = max([d.textlength(r[c], font=small) for r in rows if c < len(r)] + [28])
        widths.append(int(min(max(longest + 10, 40), 130)))
    x0, y0, rh = 22, 14, 13
    d.rectangle([0, 0, W, y0], fill=HEAD)
    d.rectangle([0, 0, x0, H], fill=HEAD)
    x = x0
    for c, w in enumerate(widths):
        d.text((x + w / 2 - 3, 2), chr(65 + c), fill=MUTED, font=_font(9))
        x += w
        d.line([x, 0, x, H], fill=GRID)
    for r in range((H - y0) // rh + 1):
        y = y0 + r * rh
        d.line([0, y, W, y], fill=GRID)
        d.text((4, y + 1), str(r + 1), fill=MUTED, font=_font(9))
        if r < len(rows):
            x = x0
            for c, w in enumerate(widths):
                if c < len(rows[r]) and rows[r][c]:
                    val = rows[r][c]
                    font = bold if r == 0 else small
                    color = (26, 115, 232) if val.startswith("=") else INK
                    d.text((x + 3, y + 1), _fit(d, val, font, w - 6), fill=color, font=font)
                x += w
    return img


def _docx(path: Path) -> Image.Image:
    from ..tools.word import para_markup

    img = Image.new("RGB", (W, H), PAGE)
    d = ImageDraw.Draw(img)
    doc = Document(path)
    x, y, width = 48, 26, W - 96
    for p in doc.paragraphs[:40]:
        text = _t(para_markup(p)).strip()
        style = p.style.name if p.style is not None else ""
        if style == "Title" or style.startswith("Heading 1"):
            font, gap, color = _font(17, True), 6, INK
        elif style.startswith("Heading"):
            font, gap, color = _font(13, True), 4, INK
        else:
            font, gap, color = _font(10), 3, (60, 64, 67)
        if not text:
            y += 6
            continue
        bullet = "List" in style
        for line in _wrap(d, ("• " if bullet else "") + text, font, width, 4):
            d.text((x, y), line, fill=color, font=font)
            y += font.size + 3
        y += gap
        if y > H - 10:
            break
    if doc.tables and y < H - 40:
        t = doc.tables[0]
        cols = len(t.columns)
        cw = width / max(cols, 1)
        for ri, row in enumerate(t.rows[:6]):
            for ci, cell in enumerate(row.cells[:cols]):
                box = [x + ci * cw, y, x + (ci + 1) * cw, y + 14]
                d.rectangle(box, outline=GRID, fill=HEAD if ri == 0 else PAGE)
                d.text((box[0] + 3, y + 1), _fit(d, _t(cell.text), _font(9, ri == 0), int(cw) - 6), fill=INK,
                       font=_font(9, ri == 0))
            y += 14
    return img


def _rgb(color_format):
    try:
        return tuple(int(str(color_format.rgb)[i:i + 2], 16) for i in (0, 2, 4))
    except (AttributeError, TypeError, ValueError):
        return None


def _pptx(path: Path) -> Image.Image:
    from ..tools.pptx_math import all_shapes, shape_markup

    prs = Presentation(path)
    if not len(prs.slides):
        return Image.new("RGB", (W, H), PAGE)
    s = prs.slides[0]
    bg = PAGE
    try:
        if s.background.fill.type is not None:
            bg = _rgb(s.background.fill.fore_color) or PAGE
    except (AttributeError, TypeError):
        pass
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    dark_bg = sum(bg) < 380
    sx, sy = W / prs.slide_width, H / prs.slide_height
    for sh in all_shapes(s):
        box = [int(sh.left * sx), int(sh.top * sy), int((sh.left + sh.width) * sx), int((sh.top + sh.height) * sy)] \
            if sh.left is not None else [24, 24, W - 24, H - 24]
        if sh.shape_type == 13:  # ảnh
            d.rectangle(box, fill=(200, 205, 212))
            continue
        if getattr(sh, "has_chart", False) and sh.has_chart:
            n = 5
            bw = (box[2] - box[0]) / (n * 1.6)
            for i in range(n):
                h = (box[3] - box[1]) * (0.35 + 0.12 * i)
                d.rectangle([box[0] + i * bw * 1.6, box[3] - h, box[0] + i * bw * 1.6 + bw, box[3]], fill=(0, 114, 178))
            continue
        if not sh.has_text_frame or not shape_markup(sh).strip():
            continue
        is_title = sh.is_placeholder and sh.placeholder_format.idx in (0, 3)
        size = 22 if is_title else 12
        font = _font(size, is_title)
        color = None
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                try:
                    color = _rgb(r.font.color) if r.font.color and r.font.color.type is not None else color
                except AttributeError:
                    pass
                break
            break
        color = color or ((240, 237, 230) if dark_bg else INK)
        y = box[1] + 4
        width = max(box[2] - box[0] - 8, 40)
        for text in shape_markup(sh).split("\n"):
            text = _t(text).strip()
            if not text:
                continue
            prefix = "" if is_title else "• "
            for line in _wrap(d, prefix + text, font, width, 2 if is_title else 1):
                tw = d.textlength(line, font=font)
                lx = box[0] + (box[2] - box[0] - tw) / 2 if is_title and sh.placeholder_format.idx == 0 and \
                    s.slide_layout.name.lower().startswith("title slide") else box[0] + 4
                d.text((lx, y), line, fill=color, font=font)
                y += size + 5
            if y > box[3]:
                break
    return img


def build(src: Path, kind: str, cache: Path) -> bytes:
    """PNG thu nhỏ của tệp `src`; `cache` là đường dẫn tệp PNG để lưu lại."""
    if cache.exists():
        return cache.read_bytes()
    img = None
    if kind in ("docx", "pptx") and render.available():
        try:
            pages = render.render(src, cache.parent / f"{cache.stem}-pages")
            if pages:
                img = Image.open(pages[0]).convert("RGB")
                img = img.crop((0, 0, img.width, min(img.height, int(img.width * H / W))))
        except render.RenderError:
            img = None
    if img is None:
        img = {"xlsx": _xlsx, "docx": _docx, "pptx": _pptx}[kind](src)
    img.thumbnail((W, H))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(buf.getvalue())
    return buf.getvalue()

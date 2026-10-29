"""Tự kiểm tra bố cục slide không cần LibreOffice: chữ tràn khung, hình chồng lấn, hình ra ngoài slide.

Chữ tràn: đo độ rộng chữ thật bằng font cùng kích thước (Arial → Liberation Sans → DejaVu Sans, DejaVu rộng hơn nên
nếu phải dùng thì ước lượng thiên về an toàn), xuống dòng theo từ như PowerPoint, so chiều cao các dòng với chiều
cao khung trừ lề trong. Cỡ chữ: lấy từ run; không có thì từ placeholder của layout/master; cuối cùng 18 pt.
Bộ đo tỉ lệ phát hiện: eval/layout_eval.py (mục 8.3 của đề xuất, mục tiêu ≥ 80%).
"""
import math
import re
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.oxml.ns import qn

from .pptx_math import all_shapes, shape_markup

EMU_PER_PT = 12700
_FONTS = {
    False: ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    True: ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
           "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
}
OVERLAP_RATIO = 0.15  # chồng lên > 15% diện tích hình nhỏ hơn mới tính là lỗi
LINE_SPACING = 1.2
INSET_PT = 7.2 + 7.2  # lề trong mặc định trên + dưới (0,1 inch mỗi bên)
SIDE_INSET_PT = 7.2 * 2


@lru_cache(maxsize=8)
def _font(bold: bool):
    for path in _FONTS[bold]:
        if Path(path).exists():
            return ImageFont.truetype(path, 100)  # đo ở cỡ 100 rồi nhân tỉ lệ
    return ImageFont.load_default(size=100)


def _text_width_pt(text: str, size_pt: float, bold: bool) -> float:
    return _font(bold).getlength(text) * size_pt / 100


def _lines(text: str, width_pt: float, size_pt: float, bold: bool) -> int:
    """Số dòng khi xuống dòng theo từ trong khung rộng width_pt."""
    if not text.strip():
        return 1
    count, cur = 1, ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if _text_width_pt(trial, size_pt, bold) <= width_pt or not cur:
            cur = trial
            # Một từ dài hơn cả khung: PowerPoint ngắt giữa từ
            extra = math.ceil(_text_width_pt(cur, size_pt, bold) / width_pt) - 1 if width_pt > 0 else 0
            if extra > 0:
                count += extra
                cur = ""
        else:
            count += 1
            cur = word
    return count


def _master_size(shape, level: int = 0) -> float | None:
    """Cỡ chữ mặc định của placeholder: lstStyle của layout → txStyles của master."""
    if not shape.is_placeholder:
        return None
    try:
        ph_type = shape.placeholder_format.type
        layout_ph = shape.part.slide.slide_layout.placeholders.get(idx=shape.placeholder_format.idx) \
            if hasattr(shape.part, "slide") else None
    except (AttributeError, KeyError, ValueError):
        ph_type, layout_ph = None, None
    lvl_tag = qn(f"a:lvl{level + 1}pPr")
    if layout_ph is not None:
        rpr = layout_ph._element.find(f".//{qn('a:lstStyle')}/{lvl_tag}/{qn('a:defRPr')}")
        if rpr is not None and rpr.get("sz"):
            return int(rpr.get("sz")) / 100
    try:
        styles = shape.part.slide.slide_layout.slide_master._element.find(qn("p:txStyles"))
    except AttributeError:
        return None
    if styles is None:
        return None
    is_title = ph_type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)
    style = styles.find(qn("p:titleStyle" if is_title else "p:bodyStyle"))
    rpr = style.find(f"{lvl_tag}/{qn('a:defRPr')}") if style is not None else None
    return int(rpr.get("sz")) / 100 if rpr is not None and rpr.get("sz") else None


def _para_size(shape, p) -> tuple[float, bool]:
    sizes = [r.font.size.pt for r in p.runs if r.font.size is not None]
    bold = any(r.font.bold for r in p.runs)
    if sizes:
        return max(sizes), bold
    end = p._p.find(qn("a:endParaRPr"))
    if end is not None and end.get("sz"):
        return int(end.get("sz")) / 100, bold
    return _master_size(shape, p.level) or 18.0, bold


def _needed_pt(shape) -> float:
    """Chiều cao chữ cần (pt), chưa tính lề trong."""
    tf = shape.text_frame
    width_pt = shape.width / EMU_PER_PT - SIDE_INSET_PT
    used = 0.0
    for p, text in zip(tf.paragraphs, shape_markup(shape).split("\n")):
        size, bold = _para_size(shape, p)
        # Công thức $...$ hiển thị gọn hơn mã LaTeX: ước lượng bằng nửa độ dài
        text = re.sub(r"\$\$?([^$]+)\$\$?", lambda m: "x" * max(1, len(m.group(1)) // 2), text)
        bullet = shape.is_placeholder and p.level == 0 and not _is_title(shape) and text.strip()
        used += _lines(text, max(width_pt - (18.0 if bullet else 0.0), 10), size, bold) * size * LINE_SPACING
    return used


def _autofit(shape) -> str | None:
    body_pr = shape.text_frame._txBody.find(qn("a:bodyPr"))
    if body_pr is None:
        return None
    if body_pr.find(qn("a:spAutoFit")) is not None:
        return "grow"  # khung tự giãn theo chữ
    if body_pr.find(qn("a:normAutofit")) is not None:
        return "shrink"  # chữ tự thu nhỏ (tới ~55%)
    return None


def _overflow(shape, slide_h: int) -> dict | None:
    if not shape.has_text_frame or shape.width is None or shape.height is None:
        return None
    used = _needed_pt(shape)
    height_pt = shape.height / EMU_PER_PT - INSET_PT
    fit = _autofit(shape)
    if fit == "grow":
        if shape.top + (used + INSET_PT) * EMU_PER_PT > slide_h + EMU_PER_PT * 2:
            return {"kind": "overflow", "detail": "khung tự giãn theo chữ và bị đẩy ra ngoài mép dưới slide — rút gọn "
                                                  "chữ hoặc dời hộp lên"}
        return None
    if used > height_pt * (1.8 if fit == "shrink" else 1.05):
        return {"kind": "overflow", "detail": f"chữ cần ~{used / 28.35:.1f} cm chiều cao, khung chỉ "
                                              f"{height_pt / 28.35:.1f} cm — rút gọn, giảm cỡ chữ hoặc tách slide"}
    return None


def _is_title(shape) -> bool:
    try:
        return shape.is_placeholder and shape.placeholder_format.type in (PP_PLACEHOLDER.TITLE,
                                                                          PP_PLACEHOLDER.CENTER_TITLE)
    except ValueError:
        return False


def _box(shape):
    """Khung thực tế: hộp chữ tự giãn (spAutoFit) cao theo chữ, không theo chiều cao lưu trong tệp."""
    if None in (shape.left, shape.top, shape.width, shape.height):
        return None
    height = shape.height
    if shape.has_text_frame and _autofit(shape) == "grow":
        height = max(height, int((_needed_pt(shape) + INSET_PT) * EMU_PER_PT))
    return shape.left, shape.top, shape.left + shape.width, shape.top + height


def _has_content(shape) -> bool:
    if shape.has_text_frame:
        return bool(shape_markup(shape).strip())
    return True  # ảnh, bảng, biểu đồ, hình vẽ


def check_slide(slide, slide_w: int, slide_h: int) -> list[dict]:
    issues = []
    shapes = [(i, sh) for i, sh in enumerate(all_shapes(slide)) if _box(sh) is not None and _has_content(sh)]
    for i, sh in shapes:
        x1, y1, x2, y2 = _box(sh)
        tol = 12700 * 2  # 2 pt
        if x1 < -tol or y1 < -tol or x2 > slide_w + tol or y2 > slide_h + tol:
            issues.append({"shape": i, "name": sh.name, "kind": "offslide",
                           "detail": "hình nằm (một phần) ngoài slide — dời vào trong hoặc thu nhỏ"})
        if (o := _overflow(sh, slide_h)) is not None:
            issues.append({"shape": i, "name": sh.name, **o})
    for a in range(len(shapes)):
        for b in range(a + 1, len(shapes)):
            (i, sa), (j, sb) = shapes[a], shapes[b]
            ax1, ay1, ax2, ay2 = _box(sa)
            bx1, by1, bx2, by2 = _box(sb)
            inter = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
            smaller = min((ax2 - ax1) * (ay2 - ay1), (bx2 - bx1) * (by2 - by1)) or 1
            if inter / smaller > OVERLAP_RATIO:
                issues.append({"shape": i, "other": j, "name": f"{sa.name} / {sb.name}", "kind": "overlap",
                               "detail": f"chồng lên nhau {inter / smaller:.0%} diện tích hình nhỏ hơn"})
    return issues


def check_presentation(prs, slides: list[int] | None = None) -> list[dict]:
    out = []
    for i, s in enumerate(prs.slides):
        if slides is not None and i not in slides:
            continue
        out += [{"slide": i, **it} for it in check_slide(s, prs.slide_width, prs.slide_height)]
    return out

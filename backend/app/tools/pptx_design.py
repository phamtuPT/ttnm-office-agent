"""Mẫu thiết kế slide.

Mẫu là tệp .pptx thật (app/resources/templates/), dựng bằng scripts/build_templates.py từ mẫu mặc định của
python-pptx: kéo giãn master/layout sang 16:9, chữ và nền dùng màu của bảng màu chủ đề (scheme color), thêm dải nhấn.
Đổi bảng màu (clean/midnight/warm) = sửa a:clrScheme trong theme → mọi slide, kể cả slide thêm sau và biểu đồ,
tự đổi theo. Người dùng cũng có thể dùng tệp .pptx của mình (mẫu công ty) làm mẫu.
"""
import copy
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE, PP_PLACEHOLDER
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.util import Cm, Emu

TEMPLATES = Path(__file__).resolve().parent.parent / "resources" / "templates"
BUILT_IN = {"default_theme": TEMPLATES / "default_theme.pptx", "default_plain": TEMPLATES / "default_plain.pptx"}
SLIDE_16_9 = (Emu(12192000), Emu(6858000))
A = "http://schemas.openxmlformats.org/drawingml/2006/main"

# Bảng màu: nền (lt1), chữ (dk1), tiêu đề (dk2), nền phụ (lt2), 6 màu nhấn — nhấn theo Okabe–Ito (an toàn cho người
# mù màu), tương phản chữ/nền ≥ 7:1 để đọc được trên máy chiếu.
PALETTES = {
    "clean": {"lt1": "FFFFFF", "dk1": "2E3A46", "dk2": "16324F", "lt2": "EEF2F6",
              "accents": ["0072B2", "E69F00", "009E73", "D55E00", "CC79A7", "56B4E9"]},
    "midnight": {"lt1": "0F1923", "dk1": "F0EDE6", "dk2": "FFB830", "lt2": "1E2F42",
                 "accents": ["56B4E9", "E69F00", "009E73", "D55E00", "CC79A7", "F0E442"]},
    "warm": {"lt1": "FBF6EE", "dk1": "3A2E26", "dk2": "C2410C", "lt2": "F3E8D8",
             "accents": ["D55E00", "0072B2", "009E73", "E69F00", "CC79A7", "56B4E9"]},
}
FONT = "Arial"  # có sẵn trên Windows/macOS; Linux/Docker dùng Liberation Sans cùng kích thước chữ


def _theme_part(prs):
    return prs.slide_master.part.part_related_by(RT.THEME)


def apply_palette(prs, name: str) -> None:
    pal = PALETTES[name]
    part = _theme_part(prs)
    root = etree.fromstring(part.blob)
    scheme = root.find(f".//{{{A}}}clrScheme")
    colors = {"dk1": pal["dk1"], "lt1": pal["lt1"], "dk2": pal["dk2"], "lt2": pal["lt2"],
              **{f"accent{i + 1}": c for i, c in enumerate(pal["accents"])}}
    for slot, hex_ in colors.items():
        el = scheme.find(f"{{{A}}}{slot}")
        for c in list(el):
            el.remove(c)
        etree.SubElement(el, f"{{{A}}}srgbClr").set("val", hex_)
    scheme.set("name", f"Office Agent {name}")
    part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def new_presentation(template: Path, palette: str | None) -> Presentation:
    """Mở mẫu, bỏ mọi slide có sẵn (giữ master/layout/theme), đổi bảng màu nếu có."""
    prs = Presentation(str(template))
    ids = prs.slides._sldIdLst
    for sld in list(ids):
        prs.part.drop_rel(sld.rId)
        ids.remove(sld)
    if palette:
        apply_palette(prs, palette)
    return prs


def find_layout(prs, kind: str):
    """Tìm layout theo vai trò (mẫu người dùng đặt tên layout tuỳ ý → nhận theo loại placeholder)."""
    def types(layout):
        return {ph.placeholder_format.type for ph in layout.placeholders}

    def body_count(layout):
        return sum(ph.placeholder_format.type in (PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT)
                   for ph in layout.placeholders)

    layouts = list(prs.slide_layouts)
    title = {PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE}
    tests = {
        "title": lambda l: PP_PLACEHOLDER.CENTER_TITLE in types(l),
        "section": lambda l: "section" in l.name.lower() or "đề mục" in l.name.lower(),
        "title_content": lambda l: bool(types(l) & title) and body_count(l) == 1,
        "title_only": lambda l: PP_PLACEHOLDER.TITLE in types(l) and body_count(l) == 0
        and PP_PLACEHOLDER.SUBTITLE not in types(l),
        "blank": lambda l: not (types(l) & title) and body_count(l) == 0,
    }
    fallback = {"title": "title_content", "section": "title_content", "title_only": "title_content",
                "blank": "title_only", "title_content": None}
    while kind:
        hit = next((l for l in layouts if tests[kind](l)), None)
        if hit is not None:
            return hit
        kind = fallback[kind]
    return layouts[0]


# ── Dựng tệp mẫu (scripts/build_templates.py) ─────────────────────────────────────────────────────────────────


def _scale_x(root, factor: float) -> None:
    for xfrm in root.iter(qn("a:xfrm")):
        off, ext = xfrm.find(qn("a:off")), xfrm.find(qn("a:ext"))
        if off is not None:
            off.set("x", str(int(int(off.get("x")) * factor)))
        if ext is not None:
            ext.set("cx", str(int(int(ext.get("cx")) * factor)))


def _scheme_fill(color: str) -> etree._Element:
    fill = etree.Element(qn("a:solidFill"))
    etree.SubElement(fill, qn("a:schemeClr")).set("val", color)
    return fill


def _style(lvl, size_pt: float, color: str, bold: bool = False, font: str = "+mn-lt") -> None:
    rpr = lvl.find(qn("a:defRPr"))
    if rpr is None:
        rpr = etree.SubElement(lvl, qn("a:defRPr"))
    rpr.set("sz", str(int(size_pt * 100)))
    rpr.set("b", "1" if bold else "0")
    for old in rpr.findall(qn("a:solidFill")):
        rpr.remove(old)
    rpr.insert(0, _scheme_fill(color))
    for old in rpr.findall(qn("a:latin")):
        rpr.remove(old)
    etree.SubElement(rpr, qn("a:latin")).set("typeface", font)


def build_template(out: Path, accent: bool) -> None:
    prs = Presentation()
    factor = SLIDE_16_9[0] / prs.slide_width
    prs.slide_width, prs.slide_height = SLIDE_16_9
    master = prs.slide_master
    _scale_x(master._element, factor)
    for layout in prs.slide_layouts:
        _scale_x(layout._element, factor)

    # Phông chữ chủ đề (tiêu đề + nội dung) và bảng màu mặc định
    part = _theme_part(prs)
    root = etree.fromstring(part.blob)
    for tag in ("majorFont", "minorFont"):
        latin = root.find(f".//{{{A}}}{tag}/{{{A}}}latin")
        latin.set("typeface", FONT)
    part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    apply_palette(prs, "clean")

    # Kiểu chữ: tiêu đề dk2 (tx2), nội dung dk1 (tx1); cỡ chữ đọc được từ cuối phòng
    styles = master._element.find(qn("p:txStyles"))
    title_lvl = styles.find(qn("p:titleStyle")).find(qn("a:lvl1pPr"))
    _style(title_lvl, 36, "tx2", bold=True, font="+mj-lt")
    title_lvl.set("algn", "l")
    body = styles.find(qn("p:bodyStyle"))
    for i, size in enumerate((22, 20, 18, 16, 16), start=1):
        lvl = body.find(qn(f"a:lvl{i}pPr"))
        if lvl is not None:
            _style(lvl, size, "tx1")
            spc = lvl.find(qn("a:spcBef"))
            if spc is None:
                spc = etree.Element(qn("a:spcBef"))
                lvl.insert(0, spc)
            for c in list(spc):
                spc.remove(c)
            etree.SubElement(spc, qn("a:spcPts")).set("val", "900")

    # Tiêu đề slide nằm sát lề trên; nội dung bắt đầu ngay dưới
    for sh in master.placeholders:
        t = sh.placeholder_format.type
        if t == PP_PLACEHOLDER.TITLE:
            sh.left, sh.top, sh.width, sh.height = Cm(1.9), Cm(0.9), Cm(30.1), Cm(2.4)
        elif t == PP_PLACEHOLDER.BODY:
            sh.left, sh.top, sh.width, sh.height = Cm(1.9), Cm(3.9), Cm(30.1), Cm(13.2)

    if accent:
        # Dải nhấn bên trái mọi slide + vạch dưới tiêu đề (màu accent1 → đổi theo bảng màu)
        # MasterShapes không có add_shape → vẽ trên slide nháp rồi chuyển phần tử sang master
        scratch = prs.slides.add_slide(prs.slide_layouts[6])
        strip = scratch.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Cm(0.45), prs.slide_height)
        line = scratch.shapes.add_shape(MSO_SHAPE.RECTANGLE, Cm(1.9), Cm(3.35), Cm(3.2), Cm(0.16))
        for shp, name in ((strip, "Dải nhấn"), (line, "Vạch tiêu đề")):
            shp.name = name
            spPr = shp._element.spPr
            for old in spPr.findall(qn("a:solidFill")):
                spPr.remove(old)
            spPr.insert(2, _scheme_fill("accent1"))
            ln = etree.SubElement(spPr, qn("a:ln"))
            etree.SubElement(ln, qn("a:noFill"))
            style = shp._element.find(qn("p:style"))
            if style is not None:
                shp._element.remove(style)
        # Hình nền đứng sau placeholder: chuyển lên đầu cây shape
        # Dải nhấn trên master (mọi slide); vạch dưới tiêu đề chỉ ở layout có tiêu đề thường (không ở slide
        # tiêu đề/đề mục/trống). Chèn ngay sau nvGrpSpPr, grpSpPr → nằm dưới placeholder.
        master.shapes._spTree.insert(2, strip._element)  # lxml: chèn vào cây mới = chuyển khỏi slide nháp
        for layout in prs.slide_layouts:
            if PP_PLACEHOLDER.TITLE in {ph.placeholder_format.type for ph in layout.placeholders} \
                    and "section" not in layout.name.lower() and "vertical" not in layout.name.lower():
                layout.shapes._spTree.insert(2, copy.deepcopy(line._element))
        ids = prs.slides._sldIdLst
        prs.part.drop_rel(ids[0].rId)
        ids.remove(ids[0])

    # Slide tiêu đề: tiêu đề lớn căn trái, phụ đề màu nhấn
    title_layout = prs.slide_layouts[0]
    for ph in title_layout.placeholders:
        t = ph.placeholder_format.type
        if t == PP_PLACEHOLDER.CENTER_TITLE:
            ph.left, ph.top, ph.width, ph.height = Cm(2.5), Cm(5.2), Cm(28.5), Cm(4.6)
        elif t == PP_PLACEHOLDER.SUBTITLE:
            ph.left, ph.top, ph.width, ph.height = Cm(2.5), Cm(10.2), Cm(28.5), Cm(3.0)
    for ph in title_layout.placeholders:
        body_pr = ph._element.find(qn("p:txBody"))
        if body_pr is None:
            continue
        lst = body_pr.find(qn("a:lstStyle"))
        if lst is None:
            continue
        for c in list(lst):
            lst.remove(c)
        lvl = etree.SubElement(lst, qn("a:lvl1pPr"))
        lvl.set("algn", "l")
        lvl.set("indent", "0")
        lvl.set("marL", "0")
        is_title = ph.placeholder_format.type == PP_PLACEHOLDER.CENTER_TITLE
        etree.SubElement(lvl, qn("a:buNone"))
        _style(lvl, 44 if is_title else 22, "tx2" if is_title else "accent1", bold=is_title,
               font="+mj-lt" if is_title else "+mn-lt")

    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))

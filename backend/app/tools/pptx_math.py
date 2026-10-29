"""Công thức toán trong PowerPoint.

PowerPoint (2010+) lưu công thức là <a14:m><m:oMath>…</m:oMath></a14:m> trong đoạn văn của shape, và bọc cả shape
trong <mc:AlternateContent>: nhánh <mc:Choice Requires="a14"> là shape thật, nhánh <mc:Fallback> cho phần mềm không
hiểu công thức (ở đây: cùng shape nhưng công thức thay bằng chữ LaTeX). python-pptx bỏ qua AlternateContent, nên mọi
tool PowerPoint lấy danh sách shape qua all_shapes() thay vì slide.shapes.
"""
import copy

from lxml import etree
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.shapes.shapetree import SlideShapeFactory

from . import omml

MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
A14 = "http://schemas.microsoft.com/office/drawing/2010/main"
AC = f"{{{MC}}}AlternateContent"
A14_M = f"{{{A14}}}m"
SHAPE_TAGS = {qn("p:sp"), qn("p:grpSp"), qn("p:graphicFrame"), qn("p:cxnSp"), qn("p:pic"), qn("p:contentPart")}


def _choice_shape(ac):
    choice = ac.find(f"{{{MC}}}Choice")
    return next((c for c in choice if c.tag in SHAPE_TAGS), None) if choice is not None else None


def all_shapes(slide) -> list:
    """Mọi shape theo thứ tự trên slide, kể cả shape chứa công thức (nằm trong AlternateContent)."""
    out = []
    for el in slide.shapes._spTree:
        if el.tag in SHAPE_TAGS:
            out.append(SlideShapeFactory(el, slide.shapes))
        elif el.tag == AC and (inner := _choice_shape(el)) is not None:
            out.append(SlideShapeFactory(inner, slide.shapes))
    return out


def _para_markup(p) -> str:
    out = []
    for c in p:
        if c.tag == qn("a:r") or c.tag == qn("a:fld"):
            out.append("".join(t.text or "" for t in c.iter(qn("a:t"))))
        elif c.tag == qn("a:br"):
            out.append("\v")
        elif c.tag == A14_M:
            for m in c:
                if etree.QName(m).localname == "oMathPara":
                    out.append("$$" + omml.to_latex(m) + "$$")
                elif etree.QName(m).localname == "oMath":
                    out.append("$" + omml.to_latex(m) + "$")
    return "".join(out)


def shape_markup(shape) -> str:
    """Chữ của shape (mỗi đoạn một dòng), công thức dạng $...$ / $$...$$."""
    if not shape.has_text_frame:
        return ""
    return "\n".join(_para_markup(p) for p in shape.text_frame._txBody.iter(qn("a:p")))


def has_math(shape) -> bool:
    return shape.has_text_frame and next(shape.text_frame._txBody.iter(A14_M), None) is not None


def _run(text: str, rpr) -> etree._Element:
    # OxmlElement: phần tử mang lớp riêng của python-pptx (p.runs, font...) như khi python-pptx tự tạo
    r = OxmlElement("a:r")
    if rpr is not None:
        r.append(copy.deepcopy(rpr))
    t = OxmlElement("a:t")
    t.text = text
    r.append(t)
    return r


def _math(latex: str, display: bool) -> etree._Element:
    m = etree.Element(A14_M, nsmap={"a14": A14})
    if display:
        para = omml.latex_to_omml_para(latex, host="pptx")
        pr = etree.Element(f"{{{omml.M}}}oMathParaPr")
        etree.SubElement(pr, f"{{{omml.M}}}jc").set(f"{{{omml.M}}}val", "centerGroup")
        para.insert(0, pr)
        m.append(para)
    else:
        m.append(omml.latex_to_omml(latex, host="pptx"))
    return m


def write_text(shape, text: str) -> None:
    """Thay chữ của shape, giữ định dạng đoạn/chữ đầu tiên; mỗi dòng một đoạn; $...$ / $$...$$ → công thức."""
    body = shape.text_frame._txBody
    paras = body.findall(qn("a:p"))
    ppr = paras[0].find(qn("a:pPr")) if paras else None
    first_r = next(body.iter(qn("a:r")), None)
    rpr = first_r.find(qn("a:rPr")) if first_r is not None else None
    end_rpr = paras[0].find(qn("a:endParaRPr")) if paras else None
    for p in paras:
        body.remove(p)
    for line in omml.fix_newlines(text).split("\n"):
        p = OxmlElement("a:p")
        body.append(p)
        if ppr is not None:
            p.append(copy.deepcopy(ppr))
        parts = omml.split_math(line)
        try:
            for kind, value in parts:
                if kind == "text":
                    if value:
                        p.append(_run(value, rpr))
                else:  # $$...$$ đứng riêng cả dòng mới căn giữa như công thức riêng dòng
                    p.append(_math(value, display=kind == "display" and len(parts) == 1))
        except omml.MathError as e:
            from .registry import ToolError
            raise ToolError(f"{e}. Viết lại công thức LaTeX (ví dụ $\\frac{{a}}{{b}}$, $x^2$)")
        if end_rpr is not None:
            p.append(copy.deepcopy(end_rpr))


def _fallback(shape_el) -> etree._Element:
    """Bản dự phòng: cùng shape, công thức thay bằng chữ LaTeX."""
    fb = copy.deepcopy(shape_el)
    for m in list(fb.iter(A14_M)):
        latex = " ".join(omml.to_latex(x) for x in m)
        r = _run(latex, None)
        m.getparent().replace(m, r)
    return fb


def finalize(slide) -> None:
    """Gọi sau khi sửa chữ: shape có công thức → bọc AlternateContent; hết công thức → gỡ bọc. Đồng bộ Fallback."""
    tree = slide.shapes._spTree
    for el in list(tree):
        if el.tag == AC:
            inner = _choice_shape(el)
            if inner is None:
                continue
            if next(inner.iter(A14_M), None) is None:
                el.addprevious(inner)  # không còn công thức: trả shape về dạng thường
                tree.remove(el)
            else:
                fallback = el.find(f"{{{MC}}}Fallback")
                if fallback is not None:
                    el.remove(fallback)
                fallback = etree.SubElement(el, f"{{{MC}}}Fallback")
                fallback.append(_fallback(inner))
        elif el.tag == qn("p:sp") and next(el.iter(A14_M), None) is not None:
            ac = etree.Element(AC, nsmap={"mc": MC})
            el.addprevious(ac)
            choice = etree.SubElement(ac, f"{{{MC}}}Choice", nsmap={"a14": A14})
            choice.set("Requires", "a14")
            choice.append(el)  # chuyển shape vào nhánh Choice
            etree.SubElement(ac, f"{{{MC}}}Fallback").append(_fallback(el))

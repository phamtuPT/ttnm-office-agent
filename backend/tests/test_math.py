import pytest

from app.tools.omml import MathError, has_math, latex_to_omml, split_math, to_latex

M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

CASES = [
    r"\frac{a+b}{2}",
    r"x^2 + y_1^3",
    r"\sqrt{x}",
    r"\sqrt[3]{x+1}",
    r"\sum_{i=1}^{n} i^2",
    r"\int_0^1 f(x)\,dx",
    r"\left( \frac{1}{x} \right)",
    r"\lim_{x \to 0} \frac{\sin x}{x}",
    r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}",
    r"\hat{x} + \vec{v} + \overline{AB}",
    r"\alpha \leq \beta \neq \pi",
    r"\binom{n}{k}",
    r"\text{Hệ số } S = \pi r^2",
    r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
    r"\int_{0}^{\infty} e^{-x^2} dx = \frac{\sqrt{\pi}}{2}",
    r"\begin{cases} x+y=1 \\ x-y=0 \end{cases}",
    r"\det(A) = \begin{vmatrix} a & b \\ c & d \end{vmatrix} = ad - bc",
]


@pytest.mark.parametrize("latex", CASES)
def test_round_trip_is_stable(latex):
    """LaTeX → OMML → LaTeX → OMML → LaTeX: lần đọc thứ hai phải giống lần đầu (agent đọc/ghi lại không làm hỏng)."""
    once = to_latex(latex_to_omml(latex))
    assert to_latex(latex_to_omml(once)) == once


def test_structures_are_native_office_math():
    def tags(latex):
        return {e.tag.replace(M, "") for e in latex_to_omml(latex).iter() if isinstance(e.tag, str)}

    assert {"f", "num", "den"} <= tags(r"\frac{1}{2}")
    assert {"nary", "sub", "sup"} <= tags(r"\sum_{i=1}^n i")
    assert "rad" in tags(r"\sqrt{2}")
    assert {"d", "m", "mr"} <= tags(r"\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}")
    assert "limLow" in tags(r"\lim_{x \to 0} x")
    assert "acc" in tags(r"\hat{x}")
    nary = latex_to_omml(r"\sum_{i=1}^n i^2").find(f"{M}nary")
    assert nary.find(f"{M}e").find(f"{M}sSup") is not None  # số hạng nằm trong ∑, không đứng ngoài


def test_readable_latex():
    assert to_latex(latex_to_omml(r"\lim_{x \to 0} \frac{\sin x}{x}")) == r"\lim_{x\to 0}\frac{\sin x}{x}"
    assert to_latex(latex_to_omml(r"\binom{n}{k}")) == r"\binom{n}{k}"
    assert to_latex(latex_to_omml(r"S = \pi r^2")) == r"S=\pi r^2"
    assert "pmatrix" in to_latex(latex_to_omml(r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}"))
    assert r"\text{Hệ số }" in to_latex(latex_to_omml(r"\text{Hệ số } S"))


def test_split_math_follows_pandoc_rules():
    assert split_math(r"Diện tích $S = \pi r^2$.") == [
        ("text", "Diện tích "), ("inline", r"S = \pi r^2"), ("text", ".")]
    assert split_math("$$x^2 = 4$$") == [("display", "x^2 = 4")]
    # Tiền tệ không bị hiểu nhầm là công thức
    assert not has_math("Giá $100 và $200 mỗi tháng")
    assert not has_math("Còn lại $5")
    assert split_math(r"Phí \$5 và $x$") == [("text", "Phí $5 và "), ("inline", "x")]


def test_bad_latex_raises():
    with pytest.raises(MathError):
        latex_to_omml("")


# ---------- Word ----------

def _ex(db, chat, turn):
    from app.tools.executor import ToolExecutor

    async def yes(_n, _a):
        return True
    return ToolExecutor(db, chat.id, yes, turn_id=turn)


def _run(ex, name, args):
    import asyncio
    return asyncio.run(ex.run(name, args))


def test_word_equations_round_trip(db, chat):
    from docx import Document

    from app.versioning import store

    r = _run(_ex(db, chat, "m1"), "word_create_document", {"file": "toan.docx", "paragraphs": [
        {"text": "Phương trình bậc hai", "style": "Heading 1"},
        {"text": r"Nghiệm của $ax^2+bx+c=0$ là:"},
        {"text": r"$$x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}$$"},
        {"text": "Giá $100 và $200 không phải công thức."},
    ]})
    assert r.ok, r.data
    f = next(x for x in chat.files if x.name == "toan.docx")
    doc = Document(store.working_path(f))
    body = doc.element.body
    assert len(body.findall(f".//{M}oMathPara")) == 1 and len(body.findall(f".//{M}oMath")) == 2
    assert doc.paragraphs[3].text == "Giá $100 và $200 không phải công thức."

    paras = _run(_ex(db, chat, "m2"), "word_inspect", {"file": "toan.docx"}).data["paragraphs"]
    assert paras[1]["text"] == "Nghiệm của $ax^2+bx+c=0$ là:"
    assert paras[2]["text"] == r"$$x=\frac{-b\pm \sqrt{b^2-4ac}}{2a}$$"

    # Dịch giữ công thức → ghi được; làm mất công thức → bị chặn, tệp không đổi
    ok = _run(_ex(db, chat, "m3"), "word_rewrite_paragraphs", {"file": "toan.docx", "items": [
        {"index": 1, "text": "The roots of $ax^2+bx+c=0$ are:"}]})
    assert ok.ok, ok.data
    bad = _run(_ex(db, chat, "m4"), "word_rewrite_paragraphs", {"file": "toan.docx", "items": [
        {"index": 2, "text": "x equals minus b plus or minus root delta over 2a"}], "allow_number_changes": True})
    assert not bad.ok and "mất công thức" in bad.data["error"]
    doc = Document(store.working_path(f))
    assert len(doc.element.body.findall(f".//{M}oMath")) == 2

    sug = _run(_ex(db, chat, "m5"), "word_suggest_edit", {"file": "toan.docx", "items": [
        {"index": 1, "text": "Khác"}]})
    assert not sug.ok and "công thức" in sug.data["error"]


def test_word_insert_many_paragraphs_into_blank_document(db, chat):
    from docx import Document

    from app.versioning import blank, store

    f = store.create_file(db, chat.id, "trong.docx", blank.blank_bytes("docx"), source="blank")
    r = _run(_ex(db, chat, "i1"), "word_insert_paragraph", {"file": "trong.docx", "after_index": 0, "paragraphs": [
        {"text": "Ôn tập", "style": "Heading 1"}, {"text": "Định lý Pytago:"}, {"text": "$$a^2 + b^2 = c^2$$"}]})
    assert r.ok, r.data
    doc = Document(store.working_path(f))
    assert [p.text for p in doc.paragraphs[:2]] == ["Ôn tập", "Định lý Pytago:"] and len(doc.paragraphs) == 3
    assert len(doc.element.body.findall(f".//{M}oMathPara")) == 1


# ---------- PowerPoint ----------

MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
A14 = "{http://schemas.microsoft.com/office/drawing/2010/main}"


def test_pptx_equations(db, chat):
    from pptx import Presentation

    from app.versioning import store

    r = _run(_ex(db, chat, "p1"), "pptx_create_presentation", {"file": "toan.pptx", "theme": "midnight", "slides": [
        {"layout": "title_content", "title": "Phương trình bậc hai",
         "bullets": [r"Dạng tổng quát $ax^2+bx+c=0$", r"$$x = \frac{-b \pm \sqrt{\Delta}}{2a}$$", "Không có công thức"]},
        {"layout": "title_content", "title": "Ghi nhớ", "bullets": ["Chữ thường"]},
    ]})
    assert r.ok, r.data
    f = next(x for x in chat.files if x.name == "toan.pptx")
    prs = Presentation(store.working_path(f))
    tree = prs.slides[0].shapes._spTree
    ac = tree.find(f"{MC}AlternateContent")
    assert ac is not None and ac.find(f"{MC}Choice").get("Requires") == "a14"
    assert ac.find(f"{MC}Fallback") is not None and len(list(ac.iter(f"{A14}m"))) == 2
    assert len(list(ac.iter(f"{M}oMathPara"))) == 1
    assert prs.slides[1].shapes._spTree.find(f"{MC}AlternateContent") is None  # slide không có công thức giữ nguyên

    shapes = _run(_ex(db, chat, "p2"), "pptx_inspect", {"file": "toan.pptx"}).data["slides"][0]["shapes"]
    body = next(s for s in shapes if "Dạng tổng quát" in s["text"])
    assert body["text"].split("\n")[:2] == ["Dạng tổng quát $ax^2+bx+c=0$", r"$$x=\frac{-b\pm \sqrt{\Delta}}{2a}$$"]
    assert any(s["text"] == "Phương trình bậc hai" for s in shapes)  # tiêu đề vẫn thấy được

    # Sửa chữ shape đang chứa công thức → bỏ hết công thức → shape trở về dạng thường
    r = _run(_ex(db, chat, "p3"), "pptx_set_text", {"file": "toan.pptx", "items": [
        {"slide": 0, "shape": body["index"], "text": "Hết công thức"}]})
    assert r.ok, r.data
    prs = Presentation(store.working_path(f))
    assert prs.slides[0].shapes._spTree.find(f"{MC}AlternateContent") is None
    assert any(sh.has_text_frame and sh.text_frame.text == "Hết công thức" for sh in prs.slides[0].shapes)


def test_literal_newline_from_model():
    from app.tools.omml import fix_newlines
    assert fix_newlines(r"$a^2+b^2=c^2$\nÝ nghĩa") == "$a^2+b^2=c^2$\nÝ nghĩa"
    assert fix_newlines(r"$a \neq b$\n2 dòng") == "$a \\neq b$\n2 dòng"
    assert fix_newlines("Giá $100") == r"Giá \$100"  # $ thường được escape để tách lại vẫn là chữ


def test_syntax_talk_is_not_math():
    assert not has_math("viết công thức dạng $...$ hoặc $$...$$")


def test_word_bad_latex_is_reported_to_model(db, chat):
    r = _run(_ex(db, chat, "b1"), "word_create_document", {"file": "x.docx", "paragraphs": [
        {"text": r"$\frac{1}{$"}]})
    assert not r.ok

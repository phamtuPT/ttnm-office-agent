"""Công thức toán Office (OMML) — dùng chung cho Word và PowerPoint.

    LaTeX ──latex2mathml──> MathML ──to_omml──> OMML     (agent viết $...$ → công thức Word/PowerPoint thật)
    OMML ──to_latex──> LaTeX                              (agent đọc lại công thức có sẵn trong tài liệu)

Chỉ chuyển các phần tử MathML mà latex2mathml sinh ra (phân số, mũ/chỉ số, căn, tổng/tích phân, giới hạn, ngoặc co
giãn, ma trận, dấu mũ/gạch trên...). Phần tử lạ → giữ nội dung con, không làm hỏng tài liệu.
"""
import re

from latex2mathml.converter import convert as _latex_to_mathml
from lxml import etree

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
MML = "http://www.w3.org/1998/Math/MathML"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
MATH_FONT = "Cambria Math"

NARY = set("∑∏∐∫∬∭∮∯∰⋃⋂⋁⋀⨁⨂")
INTEGRALS = set("∫∬∭∮∯∰")
LIMIT_WORDS = {"lim", "max", "min", "sup", "inf", "limsup", "liminf", "arg max", "arg min"}
ACCENTS = {"^": "̂", "ˆ": "̂", "̂": "̂", "→": "⃗", "⃗": "⃗", "~": "̃",
           "˜": "̃", "̃": "̃", "˙": "̇", "̇": "̇", "¨": "̈", "̈": "̈",
           "ˇ": "̌", "˘": "̆", "´": "́", "`": "̀"}
OVERLINES = set("―‾¯̅_")


class MathError(ValueError):
    pass


def latex_to_mathml(latex: str) -> etree._Element:
    try:
        return etree.fromstring(_latex_to_mathml(latex).encode("utf-8"))
    except Exception as e:  # latex2mathml báo nhiều kiểu lỗi khác nhau
        raise MathError(f"Không đọc được LaTeX '{latex}': {e}") from e


# ── MathML → OMML ────────────────────────────────────────────────────────────────────────────────────────────


class _Builder:
    """host = "word" | "pptx": định dạng chữ trong m:r khác nhau (w:rPr / a:rPr)."""

    def __init__(self, host: str):
        self.host = host

    def el(self, tag: str, *children, val: str | None = None) -> etree._Element:
        e = etree.Element(f"{{{M}}}{tag}", nsmap={"m": M})
        if val is not None:
            e.set(f"{{{M}}}val", val)
        for c in children:
            if c is not None:
                e.append(c)
        return e

    def box(self, tag: str, items: list) -> etree._Element:
        """m:e / m:num / m:sup ... — OMML yêu cầu các khung này luôn có mặt, kể cả khi trống."""
        return self.el(tag, *items)

    def run(self, text: str, plain: bool = False) -> etree._Element:
        r = self.el("r")
        if plain:
            r.append(self.el("rPr", self.el("sty", val="p")))
        if self.host == "word":
            rpr = etree.SubElement(r, f"{{{W}}}rPr", nsmap={"w": W})
            fonts = etree.SubElement(rpr, f"{{{W}}}rFonts", nsmap={"w": W})
            fonts.set(f"{{{W}}}ascii", MATH_FONT)
            fonts.set(f"{{{W}}}hAnsi", MATH_FONT)
        else:
            rpr = etree.SubElement(r, f"{{{A}}}rPr", nsmap={"a": A})
            rpr.set("lang", "en-US")
            rpr.set("i", "0" if plain else "1")
            etree.SubElement(rpr, f"{{{A}}}latin", nsmap={"a": A}).set("typeface", MATH_FONT)
        t = self.el("t")
        t.text = text
        if text != text.strip():
            t.set(XML_SPACE, "preserve")
        r.append(t)
        return r

    # MathML node → danh sách phần tử OMML
    def conv(self, n) -> list:
        if not isinstance(n.tag, str):
            return []
        tag = etree.QName(n).localname
        kids = [c for c in n if isinstance(c.tag, str)]
        text = (n.text or "").replace(" ", " ")
        if tag in ("math", "mrow", "mstyle", "mpadded", "mphantom", "merror"):
            return self.seq(kids)
        if tag == "semantics":
            return self.conv(kids[0]) if kids else []
        if tag == "mi":
            plain = len(text) > 1 or n.get("mathvariant") == "normal"
            return [self.run(text, plain)] if text else []
        if tag == "mn":
            return [self.run(text)] if text else []
        if tag == "mo":
            return [self.run(text, plain=text.strip() in LIMIT_WORDS)] if text else []
        if tag == "mtext":
            return [self.run(text, plain=True)] if text else []
        if tag == "mspace":
            return []
        if tag == "mfrac":
            num, den = (kids + [None, None])[:2]
            props = [self.el("fPr", self.el("type", val="noBar"))] if n.get("linethickness") in ("0", "0pt") else []
            return [self.el("f", *props, self.box("num", self.conv(num) if num is not None else []),
                            self.box("den", self.conv(den) if den is not None else []))]
        if tag in ("msup", "msub", "msubsup", "munder", "mover", "munderover"):
            return self.script(tag, n, kids)
        if tag == "msqrt":
            return [self.el("rad", self.el("radPr", self.el("degHide", val="1")), self.box("deg", []),
                            self.box("e", self.seq(kids)))]
        if tag == "mroot":
            base, deg = (kids + [None, None])[:2]
            return [self.el("rad", self.box("deg", self.conv(deg) if deg is not None else []),
                            self.box("e", self.conv(base) if base is not None else []))]
        if tag == "mtable":
            rows = []
            for tr in kids:
                cells = [c for c in tr if isinstance(c.tag, str) and etree.QName(c).localname == "mtd"]
                rows.append(self.el("mr", *[self.box("e", self.seq(list(c))) for c in cells]))
            return [self.el("m", *rows)] if rows else []
        if tag == "mfenced":
            return [self.fence(n.get("open", "("), n.get("close", ")"), [self.seq([k]) for k in kids])]
        if tag == "menclose":
            return [self.el("borderBox", self.box("e", self.seq(kids)))]
        return self.seq(kids)

    def fence(self, beg: str, end: str, parts: list[list]) -> etree._Element:
        pr = self.el("dPr", self.el("begChr", val=beg), self.el("endChr", val=end))
        return self.el("d", pr, *[self.box("e", p) for p in (parts or [[]])])

    def seq(self, kids: list) -> list:
        # \left( ... \right): mo co giãn ở hai đầu → m:d (ngoặc tự cao theo nội dung)
        if (len(kids) >= 2 and _is_fence(kids[0], "prefix") and _is_fence(kids[-1], "postfix")):
            return [self.fence((kids[0].text or "").strip(), (kids[-1].text or "").strip(), [self.seq(kids[1:-1])])]
        if len(kids) >= 2 and _is_fence(kids[0], "prefix"):  # \begin{cases}: chỉ có ngoặc mở
            return [self.fence((kids[0].text or "").strip(), "", [self.seq(kids[1:])])]
        out, i = [], 0
        while i < len(kids):
            k = kids[i]
            if i + 2 < len(kids) and _wraps(k, kids[i + 1], kids[i + 2]):
                # ( ma trận ) / ( n trên k ): ngoặc thường của latex2mathml → ngoặc co giãn của Office
                out.append(self.fence(k.text.strip(), kids[i + 2].text.strip(), [self.conv(kids[i + 1])]))
                i += 3
                continue
            op = _nary_op(k)
            if op is not None:
                # ∑/∫: số hạng phía sau thuộc về toán tử (m:e của m:nary)
                body = self.conv(kids[i + 1]) if i + 1 < len(kids) else []
                out.append(self.nary(op, k, body))
                i += 2
                continue
            out += self.conv(k)
            i += 1
        return out

    def nary(self, op: str, node, body: list) -> etree._Element:
        tag = etree.QName(node).localname
        kids = [c for c in node if isinstance(c.tag, str)]
        sub = sup = None
        if tag in ("msub", "munder"):
            sub = kids[1]
        elif tag in ("msup", "mover"):
            sup = kids[1]
        elif tag in ("msubsup", "munderover"):
            sub, sup = kids[1], kids[2]
        pr = [self.el("chr", val=op), self.el("limLoc", val="subSup" if op in INTEGRALS else "undOvr")]
        if sub is None:
            pr.append(self.el("subHide", val="1"))
        if sup is None:
            pr.append(self.el("supHide", val="1"))
        return self.el("nary", self.el("naryPr", *pr), self.box("sub", self.conv(sub) if sub is not None else []),
                       self.box("sup", self.conv(sup) if sup is not None else []), self.box("e", body))

    def script(self, tag: str, n, kids: list) -> list:
        kids = kids + [None, None, None]
        base, a, b = kids[0], kids[1], kids[2]
        e = self.box("e", self.conv(base) if base is not None else [])
        conv = lambda x: self.conv(x) if x is not None else []  # noqa: E731
        base_text = "".join(base.itertext()).strip() if base is not None else ""
        if tag == "msup":
            return [self.el("sSup", e, self.box("sup", conv(a)))]
        if tag == "msub":
            if base_text in LIMIT_WORDS:
                return [self.el("limLow", e, self.box("lim", conv(a)))]
            return [self.el("sSub", e, self.box("sub", conv(a)))]
        if tag == "msubsup":
            return [self.el("sSubSup", e, self.box("sub", conv(a)), self.box("sup", conv(b)))]
        if tag == "munder":
            return [self.el("limLow", e, self.box("lim", conv(a)))]
        if tag == "mover":
            mark = "".join(a.itertext()).strip() if a is not None else ""
            if mark in OVERLINES or (mark and set(mark) <= OVERLINES):
                return [self.el("bar", self.el("barPr", self.el("pos", val="top")), e)]
            if mark in ACCENTS:
                return [self.el("acc", self.el("accPr", self.el("chr", val=ACCENTS[mark])), e)]
            return [self.el("limUpp", e, self.box("lim", conv(a)))]
        # munderover không phải ∑/∫ (đã xử lý ở seq)
        inner = self.el("limLow", e, self.box("lim", conv(a)))
        return [self.el("limUpp", self.box("e", [inner]), self.box("lim", conv(b)))]


def _is_fence(n, form: str) -> bool:
    return (isinstance(n.tag, str) and etree.QName(n).localname == "mo"
            and (n.get("fence") == "true" or n.get("stretchy") == "true") and n.get("form") == form)


def _wraps(open_, inner, close) -> bool:
    if any(not isinstance(x.tag, str) for x in (open_, inner, close)):
        return False
    if etree.QName(open_).localname != "mo" or etree.QName(close).localname != "mo":
        return False
    pair = ((open_.text or "").strip(), (close.text or "").strip())
    if pair not in (("(", ")"), ("[", "]"), ("{", "}"), ("|", "|"), ("‖", "‖")):
        return False
    tag = etree.QName(inner).localname
    return tag == "mtable" or (tag == "mfrac" and inner.get("linethickness") in ("0", "0pt"))


def _nary_op(n) -> str | None:
    if not isinstance(n.tag, str):
        return None
    tag = etree.QName(n).localname
    target = n
    if tag in ("msub", "msup", "msubsup", "munder", "mover", "munderover"):
        kids = [c for c in n if isinstance(c.tag, str)]
        target = kids[0] if kids else None
    if target is None or etree.QName(target).localname != "mo":
        return None
    op = (target.text or "").strip()
    return op if op in NARY else None


def latex_to_omml(latex: str, host: str = "word") -> etree._Element:
    """LaTeX → <m:oMath>. host = "word" | "pptx"."""
    latex = latex.strip()
    if not latex:
        raise MathError("Công thức trống")
    b = _Builder(host)
    return b.el("oMath", *b.conv(latex_to_mathml(latex)))


def latex_to_omml_para(latex: str, host: str = "word") -> etree._Element:
    """Công thức đứng riêng một dòng (căn giữa) → <m:oMathPara>."""
    b = _Builder(host)
    return b.el("oMathPara", latex_to_omml(latex, host))


# ── OMML → LaTeX ─────────────────────────────────────────────────────────────────────────────────────────────

_SYMBOLS = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "ε": r"\epsilon", "ϵ": r"\epsilon",
    "ζ": r"\zeta", "η": r"\eta", "θ": r"\theta", "ι": r"\iota", "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu",
    "ν": r"\nu", "ξ": r"\xi", "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau", "υ": r"\upsilon",
    "φ": r"\phi", "ϕ": r"\phi", "χ": r"\chi", "ψ": r"\psi", "ω": r"\omega", "Γ": r"\Gamma", "Δ": r"\Delta",
    "Θ": r"\Theta", "Λ": r"\Lambda", "Ξ": r"\Xi", "Π": r"\Pi", "Σ": r"\Sigma", "Φ": r"\Phi", "Ψ": r"\Psi",
    "Ω": r"\Omega", "≤": r"\leq", "≥": r"\geq", "≠": r"\neq", "≈": r"\approx", "≡": r"\equiv", "∼": r"\sim",
    "±": r"\pm", "∓": r"\mp", "×": r"\times", "÷": r"\div", "·": r"\cdot", "⋅": r"\cdot", "∞": r"\infty",
    "→": r"\to", "←": r"\leftarrow", "⇒": r"\Rightarrow", "⇔": r"\Leftrightarrow", "↔": r"\leftrightarrow",
    "∈": r"\in", "∉": r"\notin", "⊂": r"\subset", "⊆": r"\subseteq", "⊃": r"\supset", "∪": r"\cup",
    "∩": r"\cap", "∅": r"\emptyset", "∀": r"\forall", "∃": r"\exists", "∂": r"\partial", "∇": r"\nabla",
    "°": r"^{\circ}", "…": r"\ldots", "⋯": r"\cdots", "∠": r"\angle", "⊥": r"\perp", "∥": r"\parallel",
    "′": "'", "−": "-", "∣": "|", "ℝ": r"\mathbb{R}", "ℕ": r"\mathbb{N}", "ℤ": r"\mathbb{Z}", "ℚ": r"\mathbb{Q}",
}
_NARY_LATEX = {"∑": r"\sum", "∏": r"\prod", "∐": r"\coprod", "∫": r"\int", "∬": r"\iint", "∭": r"\iiint",
               "∮": r"\oint", "⋃": r"\bigcup", "⋂": r"\bigcap", "⋁": r"\bigvee", "⋀": r"\bigwedge"}
_ACC_LATEX = {"̂": r"\hat", "⃗": r"\vec", "̃": r"\tilde", "̇": r"\dot", "̈": r"\ddot",
              "̌": r"\check", "̆": r"\breve", "́": r"\acute", "̀": r"\grave", "̅": r"\bar"}
_FUNCS = {"sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp", "lim", "max", "min", "sup", "inf",
          "sinh", "cosh", "tanh", "arcsin", "arccos", "arctan", "det", "gcd", "deg", "dim", "ker", "lg"}
_LATEX_SPECIAL = {"{": r"\{", "}": r"\}", "%": r"\%", "#": r"\#", "&": r"\&", "$": r"\$"}


def _local(e) -> str:
    return etree.QName(e).localname if isinstance(e.tag, str) else ""


def _child(e, name: str):
    return next((c for c in e if _local(c) == name and etree.QName(c).namespace == M), None)


def _prop(e, pr: str, name: str, default: str | None = None) -> str | None:
    p = _child(e, pr)
    v = _child(p, name) if p is not None else None
    return v.get(f"{{{M}}}val", default) if v is not None else default


def _group(s: str) -> str:
    s = s.strip()
    return s if len(s) == 1 or re.fullmatch(r"\\[A-Za-z]+", s) else "{" + s + "}"


def _tidy(s: str) -> str:
    """Gom khoảng trắng; chỉ giữ dấu cách khi cần tách lệnh khỏi chữ cái phía sau (\\pi r, \\sin x)."""
    parts = re.split(r"(\\text\{[^}]*\})", s)
    if len(parts) > 1:  # chữ trong \text{...} giữ nguyên khoảng trắng
        return "".join(p if i % 2 else _tidy(p) for i, p in enumerate(parts))
    s = re.sub(r"\s+", " ", s).strip()

    def keep(m: re.Match) -> str:
        before, after = s[:m.start()], s[m.end():m.end() + 1]
        if before.endswith(("&", "\\\\")) or after == "&" or s[m.end():].startswith("\\\\"):
            return " "  # ô ma trận / hàng: a & b \\ c & d
        if re.search(r"\\[A-Za-z]+$", before) and after.isalnum():
            return " "  # \to 0, \pi r
        if before[-1:].isalpha() and (after.isalpha() or after == "\\"):
            return " "  # chữ trong \text{...}, x \to
        return ""

    return re.sub(" ", keep, s)


def _text(s: str) -> str:
    out = []
    for word in re.split(r"(\s+)", s):
        if word.strip() in _FUNCS:
            out.append("\\" + word.strip() + " ")
        else:
            out.append("".join(_SYMBOLS.get(ch, _LATEX_SPECIAL.get(ch, ch)) +
                               (" " if ch in _SYMBOLS and _SYMBOLS[ch].startswith("\\") and ch != "°" else "")
                               for ch in word))
    return "".join(out)


def to_latex(e) -> str:
    """Một phần tử OMML (m:oMath, m:oMathPara hoặc khung con) → LaTeX."""
    name = _local(e)
    kids = lambda: "".join(to_latex(c) for c in e if not _local(c).endswith("Pr"))  # noqa: E731
    sub = lambda n: to_latex(_child(e, n)) if _child(e, n) is not None else ""  # noqa: E731
    if name == "oMathPara":
        return r" \\ ".join(to_latex(c) for c in e if _local(c) == "oMath")
    if name == "oMath":
        return _tidy(kids())
    if name == "r":
        t = "".join(x.text or "" for x in e if _local(x) == "t")
        plain = _prop(e, "rPr", "sty") == "p"
        if plain and t.strip() and t.strip() not in _FUNCS and re.search(r"[^\W\d_]{2,}|\s", t):
            return r"\text{" + t + "}"  # chữ thường trong công thức (mtext)
        return _text(t)
    if name == "f":
        num, den = sub("num"), sub("den")
        return (r"\binom" if _prop(e, "fPr", "type") == "noBar" else r"\frac") + "{" + num + "}{" + den + "}"
    if name == "sSup":
        return _group(sub("e")) + "^" + _group(sub("sup"))
    if name == "sSub":
        return _group(sub("e")) + "_" + _group(sub("sub"))
    if name == "sSubSup":
        return _group(sub("e")) + "_" + _group(sub("sub")) + "^" + _group(sub("sup"))
    if name == "sPre":
        return "{}_" + _group(sub("sub")) + "^" + _group(sub("sup")) + _group(sub("e"))
    if name == "rad":
        deg = sub("deg")
        hidden = _prop(e, "radPr", "degHide") in ("1", "on", "true")
        return r"\sqrt" + (f"[{deg}]" if deg and not hidden else "") + "{" + sub("e") + "}"
    if name == "nary":
        op = _prop(e, "naryPr", "chr", "∫")
        s = _NARY_LATEX.get(op, op)
        if _prop(e, "naryPr", "subHide") not in ("1", "on", "true") and sub("sub"):
            s += "_" + _group(sub("sub"))
        if _prop(e, "naryPr", "supHide") not in ("1", "on", "true") and sub("sup"):
            s += "^" + _group(sub("sup"))
        return s + " " + sub("e")
    if name == "d":
        beg, end = _prop(e, "dPr", "begChr", "("), _prop(e, "dPr", "endChr", ")")
        sep = _prop(e, "dPr", "sepChr", "|")
        inner = (sep or "").join(to_latex(c) for c in e if _local(c) == "e")
        es = [c for c in e if _local(c) == "e"]
        only = [c for c in es[0] if not _local(c).endswith("Pr")] if len(es) == 1 else []
        if len(only) == 1 and _local(only[0]) == "f" and (beg, end) == ("(", ")") \
                and _prop(only[0], "fPr", "type") == "noBar":
            return to_latex(only[0])  # \binom đã gồm ngoặc
        envs = {("(", ")"): "pmatrix", ("[", "]"): "bmatrix", ("|", "|"): "vmatrix", ("{", ""): "cases"}
        if len(only) == 1 and _local(only[0]) == "m" and (beg, end) in envs:
            return to_latex(only[0]).replace("{matrix}", "{" + envs[(beg, end)] + "}")
        fix = lambda c: {"{": r"\{", "}": r"\}", "": "."}.get(c, c)  # noqa: E731
        return r"\left" + fix(beg or "") + " " + inner + r" \right" + fix(end or "")
    if name == "m":
        rows = [" & ".join(to_latex(c) for c in mr if _local(c) == "e") for mr in e if _local(mr) == "mr"]
        return r"\begin{matrix} " + r" \\ ".join(rows) + r" \end{matrix}"
    if name == "func":
        return sub("fName") + " " + sub("e")
    if name == "limLow":
        return _group(sub("e")) + "_" + _group(sub("lim"))
    if name == "limUpp":
        return _group(sub("e")) + "^" + _group(sub("lim"))
    if name == "acc":
        return _ACC_LATEX.get(_prop(e, "accPr", "chr", "̂") or "̂", r"\hat") + "{" + sub("e") + "}"
    if name == "bar":
        return (r"\underline" if _prop(e, "barPr", "pos") == "bot" else r"\overline") + "{" + sub("e") + "}"
    if name == "groupChr":
        return r"\underbrace{" + sub("e") + "}"
    if name == "eqArr":
        return r"\begin{aligned} " + r" \\ ".join(to_latex(c) for c in e if _local(c) == "e") + r" \end{aligned}"
    if name.endswith("Pr") or name in ("ctrlPr",):
        return ""
    return kids()


# ── Văn bản có $...$ ────────────────────────────────────────────────────────────────────────────────────────

# $$...$$ (công thức riêng dòng) hoặc $...$ (trong dòng) theo quy tắc của pandoc: sau $ mở và trước $ đóng không phải
# khoảng trắng, $ đóng không đứng ngay trước chữ số → "$100 và $200" vẫn là chữ thường. \$ = ký tự $.
_MATH = re.compile(r"\$\$(?P<display>.+?)\$\$|(?<![\\$])\$(?P<inline>[^\s$](?:[^$]*?[^\s\\$])?)\$(?!\d)", re.S)


def split_math(text: str) -> list[tuple[str, str]]:
    """'Diện tích $S = \\pi r^2$.' → [('text','Diện tích '), ('inline','S = \\pi r^2'), ('text','.')]."""
    out, pos = [], 0
    for m in _MATH.finditer(text):
        if not re.search(r"[\w\\]", m.group("display") or m.group("inline") or ""):
            continue  # "$...$" khi nói về cú pháp: không có chữ/số/lệnh → không phải công thức
        if m.start() > pos:
            out.append(("text", text[pos:m.start()]))
        out.append(("display", m.group("display").strip()) if m.group("display") is not None
                   else ("inline", m.group("inline")))
        pos = m.end()
    if pos < len(text):
        out.append(("text", text[pos:]))
    return [(k, v.replace(r"\$", "$") if k == "text" else v) for k, v in out]


def has_math(text: str) -> bool:
    return any(k != "text" for k, _ in split_math(text))

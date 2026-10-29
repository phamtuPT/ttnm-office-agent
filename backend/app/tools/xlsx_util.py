"""Tiện ích Excel không cần LibreOffice: kiểm tra công thức trước khi ghi, đọc thông tin biểu đồ."""
import re

from openpyxl.formula import Tokenizer
from openpyxl.utils import FORMULAE, get_column_letter
from openpyxl.utils.cell import range_boundaries

# Hàm mới (Excel 2010+/365) phải ghi kèm tiền tố _xlfn., nếu không Excel báo #NAME?
MODERN = {
    "XLOOKUP", "XMATCH", "FILTER", "SORT", "SORTBY", "UNIQUE", "SEQUENCE", "RANDARRAY", "LET", "LAMBDA",
    "IFS", "SWITCH", "MAXIFS", "MINIFS", "CONCAT", "TEXTJOIN", "TEXTSPLIT", "TEXTBEFORE", "TEXTAFTER",
    "VSTACK", "HSTACK", "TAKE", "DROP", "CHOOSECOLS", "CHOOSEROWS", "TOCOL", "TOROW", "WRAPROWS", "WRAPCOLS",
    "EXPAND", "IFNA", "DAYS", "ISOWEEKNUM", "STDEV.S", "STDEV.P", "VAR.S", "VAR.P", "PERCENTILE.INC",
    "PERCENTILE.EXC", "QUARTILE.INC", "QUARTILE.EXC", "RANK.EQ", "RANK.AVG", "MODE.SNGL", "NORM.DIST",
    "NORM.INV", "NORM.S.DIST", "T.TEST", "T.DIST", "T.INV", "T.INV.2T", "CHISQ.TEST", "F.TEST", "CONFIDENCE.T",
    "CONFIDENCE.NORM", "COVARIANCE.S", "COVARIANCE.P", "FORECAST.LINEAR", "FLOOR.MATH", "CEILING.MATH",
    "AGGREGATE", "NUMBERVALUE", "UNICHAR", "UNICODE",
}
_REF = re.compile(r"^(?:(?:'([^']+)'|([^!]+))!)?("
                  r"\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?"  # A1, A1:B2
                  r"|\$?[A-Z]{1,3}:\$?[A-Z]{1,3}"  # B:B
                  r"|\$?\d+:\$?\d+)$")  # 1:3


def check_formula(formula: str, sheetnames: list[str]) -> tuple[str, list[str]]:
    """Trả về (công thức đã chuẩn hoá, danh sách cảnh báo). Cảnh báo tương đương #NAME?, #REF! của Excel."""
    problems: list[str] = []
    try:
        tokens = Tokenizer(formula).items
    except Exception as e:
        return formula, [f"Công thức sai cú pháp: {e}"]
    depth = 0
    for t in tokens:
        if t.type == "FUNC" and t.subtype == "OPEN":
            depth += 1
            name = t.value[:-1].upper().removeprefix("_XLFN.").removeprefix("@")
            if name not in FORMULAE and name not in MODERN:
                problems.append(f"Hàm '{name}' không có trong Excel (sẽ thành #NAME?)")
        elif t.type == "FUNC" and t.subtype == "CLOSE":
            depth -= 1
        elif t.type == "OPERAND" and t.subtype == "RANGE":
            m = _REF.match(t.value)
            if m:
                sheet = m.group(1) or m.group(2)
                if sheet and sheet not in sheetnames:
                    problems.append(f"Tham chiếu tới sheet '{sheet}' không tồn tại (sẽ thành #REF!)")
            elif re.match(r"^[A-Za-z_][\w.]*$", t.value) is None:
                problems.append(f"Tham chiếu không hợp lệ: {t.value}")
    if depth != 0:
        problems.append("Thiếu hoặc thừa dấu ngoặc")

    def prefix(m: re.Match) -> str:
        return ("_xlfn." if m.group(2).upper() in MODERN else "") + m.group(2) + "("

    fixed = re.sub(r"(?<![\w.])(_xlfn\.)?([A-Za-z][A-Za-z0-9.]*)\(",
                   lambda m: m.group(0) if m.group(1) else prefix(m), formula)
    return fixed, problems


def _text(title) -> str:
    try:
        return "".join(r.t for p in title.tx.rich.p for r in (p.r or []))
    except AttributeError:
        return ""


def chart_info(ws) -> list[dict]:
    """Thông tin biểu đồ để giao diện vẽ lại bằng SVG (openpyxl không render biểu đồ)."""
    out = []
    for ch in ws._charts:
        kind = {"barChart": "bar" if getattr(ch, "type", "col") == "bar" else "column",
                "lineChart": "line", "pieChart": "pie"}.get(ch.tagname, ch.tagname)
        series = []
        for s in ch.series:
            def ref(x):
                for attr in ("numRef", "strRef"):
                    r = getattr(x, attr, None) if x is not None else None
                    if r is not None:
                        return r.f
                return None
            series.append({"values": ref(s.val), "categories": ref(s.cat),
                           "name": ref(s.tx) if s.tx is not None else None})
        try:
            anchor = f"{get_column_letter(ch.anchor._from.col + 1)}{ch.anchor._from.row + 1}"
        except AttributeError:
            anchor = None
        out.append({"type": kind, "title": _text(ch.title) if ch.title else "", "anchor": anchor, "series": series})
    return out


def split_ref(ref: str) -> tuple[str | None, str]:
    """'Doanh thu'!$B$2:$B$13 → ('Doanh thu', 'B2:B13')"""
    sheet, _, rng = ref.rpartition("!")
    return (sheet.strip("'") or None), rng.replace("$", "")


def cells_in(rng: str) -> int:
    c1, r1, c2, r2 = range_boundaries(rng)
    return (c2 - c1 + 1) * (r2 - r1 + 1)

"""Đo tỉ lệ phát hiện lỗi bố cục của pptx_check_layout (đề xuất mục 8.3: ≥ 80%).

Sinh bài trình chiếu có slide cài sẵn lỗi đã biết (tràn chữ, chồng lấn, ra ngoài slide) và slide sạch, chạy bộ kiểm
tra rồi tính: tỉ lệ phát hiện = slide lỗi được báo đúng loại / tổng slide lỗi; báo nhầm = slide sạch bị báo lỗi.

    python -m eval.layout_eval
"""
import json
import sys
from pathlib import Path

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Cm, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.tools.layout_check import check_presentation  # noqa: E402
from app.tools.pptx_design import BUILT_IN, find_layout, new_presentation  # noqa: E402
from app.tools.pptx_math import finalize, write_text  # noqa: E402

LONG = ("Doanh thu quý này tăng mạnh nhờ mở rộng kênh bán hàng trực tuyến và chương trình khách hàng thân thiết "
        "được triển khai đồng bộ tại tất cả chi nhánh trên toàn quốc")


def _slide(prs, layout, title=""):
    s = prs.slides.add_slide(find_layout(prs, layout))
    if title and s.shapes.title is not None:
        write_text(s.shapes.title, title)
    return s


def _body(s, lines):
    body = next(ph for ph in s.placeholders if ph.placeholder_format.idx == 1)
    write_text(body, "\n".join(lines))


def _box(s, kind, l, t, w, h, text="", size=18):
    sh = s.shapes.add_textbox(Cm(l), Cm(t), Cm(w), Cm(h)) if kind == "text" else \
        s.shapes.add_shape(kind, Cm(l), Cm(t), Cm(w), Cm(h))
    if text:
        write_text(sh, text)
        sh.text_frame.word_wrap = True
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                r.font.size = Pt(size)
    return sh


# (tên, loại lỗi cài sẵn hoặc None, hàm dựng slide)
CASES = [
    ("tràn: 12 gạch đầu dòng dài", "overflow", lambda p: _body(_slide(p, "title_content", "Kết quả"), [LONG] * 12)),
    ("tràn: tiêu đề quá dài", "overflow", lambda p: _slide(p, "title_content", LONG + " " + LONG)),
    ("tràn: hộp chữ sát đáy tự giãn", "overflow",
     lambda p: _box(_slide(p, "title_only", "Ghi chú"), "text", 2, 16.5, 6, 1.2, LONG)),
    ("chồng: hộp chữ giãn đè hình bên dưới", "overlap", lambda p: [
        _box(s := _slide(p, "title_only", "Ghi chú"), "text", 2, 4.5, 7, 1.2, LONG),
        _box(s, MSO_SHAPE.RECTANGLE, 2, 8, 12, 4, "Bảng tóm tắt")]),
    ("tràn: chữ trong chevron", "overflow",
     lambda p: _box(_slide(p, "title_only", "Quy trình"), MSO_SHAPE.CHEVRON, 2, 6, 5, 2, LONG, 20)),
    ("tràn: nhiều công thức", "overflow",
     lambda p: _body(_slide(p, "title_content", "Công thức"),
                     [r"$$x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}$$"] * 9 + [LONG] * 3)),
    ("chồng: hai khối đè nhau", "overlap", lambda p: [
        _box(s := _slide(p, "title_only", "So sánh"), MSO_SHAPE.ROUNDED_RECTANGLE, 2, 5, 14, 8, "Phương án A"),
        _box(s, MSO_SHAPE.ROUNDED_RECTANGLE, 9, 7, 14, 8, "Phương án B")]),
    ("chồng: hình đè lên nội dung", "overlap", lambda p: [
        _body(s := _slide(p, "title_content", "Tổng quan"), ["Ý thứ nhất", "Ý thứ hai", "Ý thứ ba"]),
        _box(s, MSO_SHAPE.OVAL, 3, 4.5, 10, 6, "Nổi bật")]),
    ("chồng: biểu đồ đè tiêu đề", "overlap", lambda p: _chart(_slide(p, "title_only", "Doanh thu theo quý"), 1.5, 0.5)),
    ("ngoài: khối tràn mép phải", "offslide",
     lambda p: _box(_slide(p, "title_only", "Lộ trình"), MSO_SHAPE.RECTANGLE, 28, 6, 9, 4, "Giai đoạn 3")),
    ("ngoài: hộp chữ trên mép trên", "offslide",
     lambda p: _box(_slide(p, "title_content", "Mốc"), "text", 20, -2.5, 8, 2, "Chú thích")),
    # Slide sạch: không được báo lỗi
    ("sạch: 4 gạch đầu dòng", None, lambda p: _body(_slide(p, "title_content", "Mục tiêu"),
                                                   ["Tăng doanh thu 15%", "Mở 3 chi nhánh", "Giảm chi phí vận hành",
                                                    "Đào tạo nhân viên mới"])),
    ("sạch: slide tiêu đề", None, lambda p: _slide(p, "title", "Báo cáo quý III")),
    ("sạch: 3 chevron cách đều", None, lambda p: [
        _box(s := _slide(p, "title_only", "Quy trình"), MSO_SHAPE.CHEVRON, 2, 6, 9.5, 3, "Thu thập"),
        _box(s, MSO_SHAPE.CHEVRON, 12, 6, 9.5, 3, "Phân tích"), _box(s, MSO_SHAPE.CHEVRON, 22, 6, 9.5, 3, "Báo cáo")]),
    ("sạch: hai khối cạnh nhau", None, lambda p: [
        _box(s := _slide(p, "title_only", "So sánh"), MSO_SHAPE.ROUNDED_RECTANGLE, 2, 5, 14, 8, "Phương án A"),
        _box(s, MSO_SHAPE.ROUNDED_RECTANGLE, 17.5, 5, 14, 8, "Phương án B")]),
    ("sạch: hai công thức", None, lambda p: _body(_slide(p, "title_content", "Định lý Pytago"),
                                                 [r"$$a^2 + b^2 = c^2$$", "Áp dụng cho tam giác vuông"])),
    ("sạch: biểu đồ trong vùng nội dung", None, lambda p: _chart(_slide(p, "title_only", "Doanh thu"), 1.9, 4.2)),
]


def _chart(s, left, top):
    data = CategoryChartData()
    data.categories = ["Q1", "Q2", "Q3", "Q4"]
    data.add_series("Doanh thu", [10, 12, 15, 14])
    s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Cm(left), Cm(top), Cm(28), Cm(12.5), data)


def evaluate() -> dict:
    rows = []
    for template in BUILT_IN:
        for palette in ("clean", "midnight", "warm"):
            prs = new_presentation(BUILT_IN[template], palette)
            for _name, _kind, build in CASES:
                build(prs)
                finalize(prs.slides[-1])
            issues = check_presentation(prs)
            for i, (name, kind, _) in enumerate(CASES):
                found = {it["kind"] for it in issues if it["slide"] == i}
                rows.append({"case": name, "template": template, "palette": palette, "expected": kind,
                             "found": sorted(found), "ok": (kind in found) if kind else not found})
    planted = [r for r in rows if r["expected"]]
    clean = [r for r in rows if not r["expected"]]
    return {
        "detection_rate": sum(r["ok"] for r in planted) / len(planted),
        "false_positive_rate": sum(not r["ok"] for r in clean) / len(clean),
        "planted": len(planted), "clean": len(clean),
        "misses": [r for r in rows if not r["ok"]],
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    result = evaluate()
    print(json.dumps({k: v for k, v in result.items() if k != "misses"}, ensure_ascii=False, indent=2))
    for m in result["misses"]:
        print("SAI:", m["case"], m["template"], m["palette"], "→ thấy", m["found"])

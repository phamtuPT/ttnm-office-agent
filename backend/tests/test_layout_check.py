import asyncio

from app.tools.executor import ToolExecutor
from eval.layout_eval import evaluate


def test_layout_detection_meets_proposal_target():
    """Đề xuất mục 8.3: tỉ lệ phát hiện lỗi bố cục ≥ 80%; báo nhầm trên slide sạch phải thấp."""
    r = evaluate()
    assert r["detection_rate"] >= 0.8, r["misses"]
    assert r["false_positive_rate"] <= 0.1, r["misses"]


def test_check_layout_tool(db, chat):
    async def yes(_n, _a):
        return True

    def run(name, args, turn):
        return asyncio.run(ToolExecutor(db, chat.id, yes, turn_id=turn).run(name, args))

    long = "Một câu rất dài để làm tràn khung nội dung của slide trình chiếu này " * 3
    assert run("pptx_create_presentation", {"file": "kt.pptx", "slides": [
        {"title": "Ổn", "bullets": ["Ngắn gọn", "Rõ ràng"]},
        {"title": "Tràn", "bullets": [long] * 8},
    ]}, "c1").ok
    r = run("pptx_check_layout", {"file": "kt.pptx"}, "c2")
    assert r.ok and r.data["checked_slides"] == 2
    assert {(i["slide"], i["kind"]) for i in r.data["issues"]} == {(1, "overflow")}
    assert run("pptx_check_layout", {"file": "kt.pptx", "slides": [0]}, "c3").data["issue_count"] == 0

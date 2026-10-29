import asyncio

from lxml import etree
from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

from app.tools.executor import ToolExecutor
from app.tools.pptx_design import BUILT_IN, find_layout, new_presentation
from app.versioning import blank, store

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def run(db, chat, name, args, turn):
    async def yes(_n, _a):
        return True
    return asyncio.run(ToolExecutor(db, chat.id, yes, turn_id=turn).run(name, args))


def lt1(prs) -> str:
    theme = etree.fromstring(prs.slide_master.part.part_related_by(RT.THEME).blob)
    return theme.find(f".//{A}lt1/{A}srgbClr").get("val")


def test_templates_are_16_9_with_scaled_layouts():
    for path in BUILT_IN.values():
        prs = Presentation(str(path))
        assert prs.slide_width == 12192000 and len(prs.slides) == 0
        body = find_layout(prs, "title_content")
        assert max(ph.left + ph.width for ph in body.placeholders) > 11_000_000  # không còn kẹt ở khổ 4:3
    prs = new_presentation(BUILT_IN["default_theme"], "midnight")
    assert lt1(prs) == "0F1923"
    assert {k: find_layout(prs, k).name for k in ("title", "title_content", "section", "title_only", "blank")} == {
        "title": "Title Slide", "title_content": "Title and Content", "section": "Section Header",
        "title_only": "Title Only", "blank": "Blank"}


def test_new_pptx_session_starts_from_template():
    import io
    prs = Presentation(io.BytesIO(blank.blank_bytes("pptx")))
    assert prs.slide_width == 12192000 and any(sh.name == "Dải nhấn" for sh in prs.slide_master.shapes)


def test_user_template_and_theme_switch(db, chat):
    r = run(db, chat, "pptx_create_presentation", {"file": "mau.pptx", "theme": "warm", "slides": [
        {"layout": "title", "title": "Mẫu công ty"}]}, "d1")
    assert r.ok, r.data
    r = run(db, chat, "pptx_create_presentation", {"file": "bao-cao.pptx", "template": "mau.pptx", "theme": "midnight",
                                                    "slides": [{"title": "Theo mẫu", "bullets": ["a"]}]}, "d2")
    assert r.ok, r.data
    f = next(x for x in chat.files if x.name == "bao-cao.pptx")
    prs = Presentation(store.working_path(f))
    assert lt1(prs) == "FBF6EE" and len(prs.slides) == 1  # giữ màu của mẫu người dùng, bỏ slide cũ của mẫu
    assert not run(db, chat, "pptx_create_presentation", {"file": "x.pptx", "template": "khong-co.pptx",
                                                          "slides": [{"title": "a"}]}, "d3").ok

    r = run(db, chat, "pptx_set_theme", {"file": "bao-cao.pptx", "theme": "clean"}, "d4")
    assert r.ok and not r.unchanged, r.data
    assert lt1(Presentation(store.working_path(f))) == "FFFFFF"


def test_create_fills_untouched_starter_file(db, chat):
    f = store.create_file(db, chat.id, "Bản trình chiếu mới.pptx", blank.blank_bytes("pptx"), source="blank")
    r = run(db, chat, "pptx_create_presentation", {"file": "Bản trình chiếu mới.pptx", "slides": [
        {"layout": "title", "title": "Mở đầu"}, {"title": "Nội dung", "bullets": ["a"]}]}, "b1")
    assert r.ok, r.data
    assert r.changes[0].version == 2  # phiên bản mới của tệp khởi đầu → hoàn tác về tệp trống được
    assert len(Presentation(store.working_path(f)).slides) == 2
    again = run(db, chat, "pptx_create_presentation", {"file": "Bản trình chiếu mới.pptx", "slides": [
        {"title": "Ghi đè"}]}, "b2")
    assert not again.ok and "Đã có tệp" in again.data["error"]  # tệp đã có nội dung thì không ghi đè

    r = run(db, chat, "pptx_add_slide", {"file": "Bản trình chiếu mới.pptx", "after": 0, "slides": [
        {"title": "Thêm 1"}, {"title": "Thêm 2"}]}, "b3")
    assert r.ok and r.data["inserted_at"] == [1, 2]
    assert [s.shapes.title.text for s in Presentation(store.working_path(f)).slides] == [
        "Mở đầu", "Thêm 1", "Thêm 2", "Nội dung"]


def test_add_shapes_diagram(db, chat):
    run(db, chat, "pptx_create_presentation", {"file": "sd.pptx", "slides": [{"layout": "title_only", "title": "Quy trình"}]}, "s1")
    r = run(db, chat, "pptx_add_shape", {"file": "sd.pptx", "slide": 0, "shapes": [
        {"kind": "chevron", "left_cm": 2, "top_cm": 6, "width_cm": 9, "height_cm": 3, "text": "Thu thập"},
        {"kind": "chevron", "left_cm": 12, "top_cm": 6, "width_cm": 9, "height_cm": 3, "text": "Phân tích", "fill": "accent2"},
        {"kind": "text_box", "left_cm": 2, "top_cm": 11, "width_cm": 20, "height_cm": 2, "text": "Lợi nhuận $P = R - C$"},
    ]}, "s2")
    assert r.ok, r.data
    assert len(r.data["shapes"]) == 3
    shapes = run(db, chat, "pptx_inspect", {"file": "sd.pptx"}, "s3").data["slides"][0]["shapes"]
    texts = [s["text"] for s in shapes]
    assert "Thu thập" in texts and "Lợi nhuận $P=R-C$" in texts
    bad = run(db, chat, "pptx_add_shape", {"file": "sd.pptx", "slide": 0, "shapes": [
        {"kind": "oval", "left_cm": 30, "top_cm": 2, "width_cm": 9, "height_cm": 3}]}, "s4")
    assert not bad.ok and "ngoài slide" in bad.data["error"]

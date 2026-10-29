import asyncio
import io

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.shared import Cm, Pt, RGBColor

from app.tools.executor import ToolExecutor
from app.versioning import store


def _run(db, chat, name, args, turn):
    async def yes(_n, _a):
        return True
    return asyncio.run(ToolExecutor(db, chat.id, yes, turn_id=turn).run(name, args))


def _bytes(doc) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_copy_style_from_template(db, chat):
    mau = Document()
    h1 = mau.styles["Heading 1"].font
    h1.size, h1.color.rgb, h1.name = Pt(20), RGBColor(0xC0, 0x00, 0x00), "Times New Roman"
    mau.styles["Normal"].font.size = Pt(13)
    sec = mau.sections[0]
    sec.orientation, sec.page_width, sec.page_height = WD_ORIENT.LANDSCAPE, sec.page_height, sec.page_width
    sec.left_margin = Cm(3)
    mau.add_paragraph("Mẫu", "Heading 1")
    store.create_file(db, chat.id, "mau.docx", _bytes(mau))

    bc = Document()
    bc.add_paragraph("Báo cáo", "Heading 1")
    p = bc.add_paragraph()
    r = p.add_run("Chữ gõ tay cỡ 9")
    r.font.size, r.bold = Pt(9), True
    bc.add_paragraph("Ý một", "List Bullet")
    f = store.create_file(db, chat.id, "bao-cao.docx", _bytes(bc))

    res = _run(db, chat, "word_copy_style", {"file": "bao-cao.docx", "source": "mau.docx",
                                             "reset_direct_formatting": True}, "cs1")
    assert res.ok, res.data
    assert res.changes and "kiểu chữ" in res.changes[0].summary  # diff phát hiện đổi styles
    doc = Document(store.working_path(f))
    h = doc.styles["Heading 1"].font
    assert (h.size, str(h.color.rgb), h.name) == (Pt(20), "C00000", "Times New Roman")
    assert doc.styles["Normal"].font.size == Pt(13)
    assert doc.sections[0].orientation == WD_ORIENT.LANDSCAPE
    assert abs(doc.sections[0].left_margin - Cm(3)) < Cm(0.01)  # Word lưu lề theo twip
    run = doc.paragraphs[1].runs[0]
    assert run.font.size is None and run.bold  # bỏ cỡ chữ gõ tay, giữ in đậm
    assert [p.text for p in doc.paragraphs] == ["Báo cáo", "Chữ gõ tay cỡ 9", "Ý một"]  # nội dung giữ nguyên
    numpr = doc.styles["List Bullet"].element.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr")
    assert numpr is not None  # gạch đầu dòng vẫn trỏ tới đánh số của chính tệp đích

    bad = _run(db, chat, "word_copy_style", {"file": "bao-cao.docx", "source": "khong-co.docx"}, "cs2")
    assert not bad.ok and "Không có tệp" in bad.data["error"]

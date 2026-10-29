import io
import os
import tempfile

# Phải đặt trước khi import app (config được cache, engine tạo lúc import)
_tmp = tempfile.mkdtemp(prefix="ttnm-test-")
os.environ["STORAGE_DIR"] = _tmp
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["LLM_PROVIDER"] = "mock"

import openpyxl  # noqa: E402
import pytest  # noqa: E402
from docx import Document  # noqa: E402
from pptx import Presentation  # noqa: E402

from app import tools  # noqa: E402, F401
from app.db import ChatSession, SessionLocal, init_db  # noqa: E402

init_db()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def chat(db):
    s = ChatSession()
    db.add(s)
    db.commit()
    return s


def xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Doanh thu"
    ws.append(["Tháng", "Doanh thu"])
    for m, v in [(1, 100), (2, 150), (3, 120)]:
        ws.append([m, v])
    wb.create_sheet("Ghi chú")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def docx_bytes() -> bytes:
    doc = Document()
    doc.add_heading("Báo cáo", 1)
    doc.add_paragraph("Đoạn một.")
    doc.add_paragraph("Đoạn hai.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def pptx_bytes() -> bytes:
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = "Tiêu đề"
    s.placeholders[1].text = "Nội dung"
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

import atexit
import io
import os
import tempfile
import uuid


def _fresh_postgres(admin_url: str) -> str:
    """Tạo một CSDL test_<ngẫu nhiên> trên máy chủ Postgres cho lượt chạy này, xoá khi xong."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = make_url(admin_url.replace("postgresql://", "postgresql+psycopg://", 1))
    name = f"test_{uuid.uuid4().hex[:10]}"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))

    def _drop() -> None:
        from app.db import engine
        engine.dispose()
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))

    atexit.register(_drop)
    return url.set(database=name).render_as_string(hide_password=False)


# Phải đặt trước khi import app (config được cache, engine tạo lúc import).
# Mặc định SQLite tạm; TEST_DATABASE_URL=postgresql://... → chạy trên Postgres thật (CSDL riêng mỗi lượt).
_tmp = tempfile.mkdtemp(prefix="ttnm-test-")
os.environ["STORAGE_DIR"] = _tmp
_pg = os.environ.get("TEST_DATABASE_URL")
os.environ["DATABASE_URL"] = _fresh_postgres(_pg) if _pg else f"sqlite:///{_tmp}/test.db"
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


def png_bytes() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "red").save(buf, "PNG")
    return buf.getvalue()

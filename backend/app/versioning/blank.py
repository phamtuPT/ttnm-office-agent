"""Tệp trống để bắt đầu phiên làm việc mới theo loại người dùng chọn ở trang chủ."""
import io

import openpyxl
from docx import Document
from pptx import Presentation
from pptx.util import Emu

# Tên tệp và tên phiên mặc định. Phiên có tên mặc định sẽ được đặt lại tên theo yêu cầu đầu tiên.
DEFAULTS = {
    "xlsx": ("Bảng tính mới.xlsx", "Bảng tính mới"),
    "docx": ("Tài liệu mới.docx", "Tài liệu mới"),
    "pptx": ("Bản trình chiếu mới.pptx", "Bản trình chiếu mới"),
}
DEFAULT_TITLES = {"Phiên mới", *(t for _, t in DEFAULTS.values())}


def blank_bytes(kind: str) -> bytes:
    buf = io.BytesIO()
    if kind == "xlsx":
        wb = openpyxl.Workbook()
        wb.active.title = "Trang tính 1"
        wb.save(buf)
    elif kind == "docx":
        Document().save(buf)
    elif kind == "pptx":
        prs = Presentation()
        prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)  # 16:9
        prs.slides.add_slide(prs.slide_layouts[0])
        prs.save(buf)
    else:
        raise ValueError(f"Không hỗ trợ loại tệp {kind}")
    return buf.getvalue()

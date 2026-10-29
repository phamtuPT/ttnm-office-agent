"""Tệp trống để bắt đầu phiên làm việc mới theo loại người dùng chọn ở trang chủ."""
import io

import openpyxl
from docx import Document

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
        from ..tools.pptx_design import BUILT_IN, find_layout, new_presentation  # import muộn: tools dùng versioning
        prs = new_presentation(BUILT_IN["default_theme"], "clean")  # 16:9, có sẵn mẫu thiết kế
        prs.slides.add_slide(find_layout(prs, "title"))
        prs.save(buf)
    else:
        raise ValueError(f"Không hỗ trợ loại tệp {kind}")
    return buf.getvalue()

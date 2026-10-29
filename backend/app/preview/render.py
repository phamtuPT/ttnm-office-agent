"""Render trang/slide thành ảnh PNG: LibreOffice headless (Office → PDF) rồi PyMuPDF (PDF → PNG).

Dùng cho (1) khung xem trước slide trên giao diện và (2) agent tự "nhìn" kết quả để phát hiện chữ tràn,
hình chồng lấn. Máy không có LibreOffice thì available() = False và hệ thống bỏ qua tính năng này.
Ảnh được cache theo phiên bản tệp: storage/<session>/renders/<file_id>/v<n>/page-<i>.png
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf

from ..config import get_settings

CONVERT_TIMEOUT_S = 90


def soffice() -> str | None:
    s = get_settings().soffice_path
    return s if s and Path(s).exists() else (shutil.which("soffice") or shutil.which("libreoffice"))


def available() -> bool:
    return soffice() is not None


class RenderError(Exception):
    pass


def to_pdf(src: Path, out_dir: Path) -> Path:
    exe = soffice()
    if exe is None:
        raise RenderError("Máy chủ chưa cài LibreOffice nên không render được trang")
    with tempfile.TemporaryDirectory() as profile:
        # Profile riêng để chạy song song được và không đụng LibreOffice người dùng đang mở
        cmd = [exe, f"-env:UserInstallation={Path(profile).as_uri()}", "--headless", "--convert-to", "pdf",
               "--outdir", str(out_dir), str(src)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=CONVERT_TIMEOUT_S)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise RenderError(f"LibreOffice không chuyển được tệp: {e}")
    pdf = out_dir / (src.stem + ".pdf")
    if not pdf.exists():
        raise RenderError("LibreOffice không tạo ra PDF")
    return pdf


def pdf_to_pngs(pdf: Path, out_dir: Path, dpi: int = 80) -> list[Path]:
    out = []
    with pymupdf.open(pdf) as doc:
        for i, page in enumerate(doc):
            p = out_dir / f"page-{i}.png"
            page.get_pixmap(dpi=dpi).save(p)
            out.append(p)
    return out


def render(src: Path, cache_dir: Path, dpi: int = 80) -> list[Path]:
    """Render cả tệp, có cache. Trả về danh sách PNG theo thứ tự trang/slide."""
    done = cache_dir / ".done"
    if done.exists():
        return sorted(cache_dir.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[1]))
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        # Chép sang tên ASCII: LibreOffice trên Windows đôi khi lỗi với tên có dấu
        src_copy = Path(tmp) / f"input{src.suffix}"
        shutil.copy2(src, src_copy)
        pages = pdf_to_pngs(to_pdf(src_copy, Path(tmp)), cache_dir, dpi)
    done.touch()
    return pages

"""OCR cục bộ (Tesseract) — đối chứng với vision LLM khi đánh giá (đề xuất mục 8.3: CER, trích xuất bảng).

Tesseract là tuỳ chọn: Docker đã cài sẵn (tesseract-ocr-vie); máy không có thì available() = False.
"""
import shutil
import subprocess
from pathlib import Path

from ..config import get_settings


def tesseract() -> str | None:
    s = get_settings().tesseract_path
    return s if s and Path(s).exists() else shutil.which("tesseract")


def available() -> bool:
    return tesseract() is not None


def ocr(image: Path, lang: str = "vie+eng", timeout: float = 60) -> str:
    exe = tesseract()
    if exe is None:
        raise RuntimeError("Máy chủ chưa cài Tesseract OCR")
    r = subprocess.run([exe, str(image), "stdout", "-l", lang, "--psm", "6"], capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "ignore")[:300])
    return r.stdout.decode("utf-8", "ignore").strip()


def _levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Tỉ lệ lỗi ký tự (Character Error Rate) = khoảng cách sửa / độ dài bản chuẩn. Bỏ qua khác biệt khoảng trắng."""
    ref, hyp = " ".join(reference.split()), " ".join(hypothesis.split())
    return _levenshtein(ref, hyp) / max(len(ref), 1)


def table_cell_accuracy(reference: list[list[str]], predicted: list[list[str]]) -> float:
    """Tỉ lệ ô đúng giá trị và đúng vị trí so với bảng chuẩn."""
    total = sum(len(r) for r in reference)
    ok = sum(1 for i, row in enumerate(reference) for j, v in enumerate(row)
             if i < len(predicted) and j < len(predicted[i]) and str(predicted[i][j]).strip() == str(v).strip())
    return ok / max(total, 1)

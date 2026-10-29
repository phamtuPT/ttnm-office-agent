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


_DIGITS = {"không": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5, "sáu": 6,
           "bảy": 7, "tám": 8, "chín": 9}


def _number_words(words: list[str]) -> list[str]:
    """"mười hai" → "12", "hai mươi lăm" → "25", "bốn" → "4": nhận dạng giọng nói viết số bằng chữ hay chữ số đều được."""
    out, i = [], 0
    while i < len(words):
        w = words[i]
        nxt = words[i + 1] if i + 1 < len(words) else ""
        if w == "mười":
            unit = _DIGITS.get(nxt)
            out.append(str(10 + unit) if unit is not None and unit else "10")
            i += 2 if unit else 1
        elif w in _DIGITS and nxt in ("mươi", "chục"):
            third = words[i + 2] if i + 2 < len(words) else ""
            unit = _DIGITS.get(third)
            out.append(str(_DIGITS[w] * 10 + (unit or 0)))
            i += 3 if unit else 2
        elif w in _DIGITS and w != "năm":  # "năm" còn nghĩa là "năm (2026)": để như chữ
            out.append(str(_DIGITS[w]))
            i += 1
        else:
            out.append(w)
            i += 1
    return out


def _words(text: str) -> list[str]:
    import re
    import unicodedata
    text = unicodedata.normalize("NFC", text.lower())
    # "15 tháng 01 năm 2026" ≡ "15/01/2026"
    text = re.sub(r"(\d{1,2}) tháng (\d{1,2}) năm (\d{4})", r"\1/\2/\3", text)
    words = [w.strip(".,:;!?-") for w in re.findall(r"[\w./:%-]+", text)]  # dấu câu cuối từ không tính là lỗi
    return _number_words([w for w in words if w])


def wer(reference: str, hypothesis: str) -> float:
    """Tỉ lệ lỗi từ (Word Error Rate) cho nhận dạng giọng nói: bỏ hoa/thường và dấu câu, giữ số như 15/01/2026."""
    ref, hyp = _words(reference), _words(hypothesis)
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1] / max(len(ref), 1)

"""Ẩn danh thông tin cá nhân trước khi gửi cho LLM trên đám mây — thuật toán tất định, KHÔNG đi qua LLM.

Email, URL, số thẻ (kiểm tra Luhn), số điện thoại Việt Nam được thay bằng nhãn ⟦EMAIL_1⟧, ⟦PHONE_2⟧...
Cùng một giá trị luôn nhận cùng một nhãn trong một phiên. Khi LLM gọi tool với nhãn (ví dụ ghi ⟦EMAIL_1⟧
vào ô), nhãn được đổi lại thành giá trị thật trước khi ghi tệp, nên tệp kết quả vẫn đúng.
Giới hạn: không che được chữ trong ảnh.
"""
import re

_PATTERNS = [
    ("URL", re.compile(r"\bhttps?://[^\s<>\"']+|\bwww\.[^\s<>\"']+", re.I)),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("CARD", re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")),
    ("PHONE", re.compile(r"(?<![\w+])(?:\+84|0)(?:[ .-]?\d){8,10}(?!\d)")),
]
_TAG = re.compile(r"⟦[A-Z]+_\d+⟧")


def _luhn(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


class Anonymizer:
    def __init__(self, mapping: dict[str, str] | None = None):
        self.mapping: dict[str, str] = dict(mapping or {})  # nhãn → giá trị thật
        self._reverse = {v: k for k, v in self.mapping.items()}

    def _tag(self, kind: str, value: str) -> str:
        if value in self._reverse:
            return self._reverse[value]
        n = sum(1 for k in self.mapping if k.startswith(f"⟦{kind}_")) + 1
        tag = f"⟦{kind}_{n}⟧"
        self.mapping[tag], self._reverse[value] = value, tag
        return tag

    def mask_text(self, text: str) -> str:
        for kind, pattern in _PATTERNS:
            def repl(m: re.Match) -> str:
                value = m.group(0)
                if kind == "CARD" and not _luhn(re.sub(r"\D", "", value)):
                    return value
                return self._tag(kind, value)
            # Không đụng vào nhãn đã có
            pieces = _TAG.split(text)
            tags = _TAG.findall(text)
            text = "".join(pattern.sub(repl, p) + (tags[i] if i < len(tags) else "") for i, p in enumerate(pieces))
        return text

    def unmask_text(self, text: str) -> str:
        return _TAG.sub(lambda m: self.mapping.get(m.group(0), m.group(0)), text)

    def mask(self, obj):
        return _walk(obj, self.mask_text)

    def unmask(self, obj):
        return _walk(obj, self.unmask_text)


def _walk(obj, fn):
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, dict):
        return {k: _walk(v, fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk(v, fn) for v in obj]
    return obj

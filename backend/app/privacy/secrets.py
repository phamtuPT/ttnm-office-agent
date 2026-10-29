"""Che chuỗi giống khoá API trong log để khoá không bao giờ bị ghi ra."""
import logging
import re

_SECRET = re.compile(
    r"AIza[0-9A-Za-z_\-]{30,}"  # Google
    r"|sk-[A-Za-z0-9_\-]{16,}"  # OpenAI
    r"|(?i:bearer)\s+[A-Za-z0-9._\-]{16,}"
    r"|(?i:api[_-]?key)[\"'=:\s]+[A-Za-z0-9._\-]{16,}"
)


def redact(text: str) -> str:
    return _SECRET.sub("[ĐÃ CHE]", text)


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        clean = redact(msg)
        if clean != msg:
            record.msg, record.args = clean, ()
        return True


def install() -> None:
    f = RedactSecretsFilter()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "httpx", "google_genai", "openai"):
        logger = logging.getLogger(name)
        logger.addFilter(f)
        for h in logger.handlers:
            h.addFilter(f)

from datetime import datetime, timezone
from typing import Iterator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..auth import owns
from ..db import ChatSession, File, SessionLocal, User


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def iso(dt: datetime) -> str:
    """Postgres trả về giờ có múi giờ; SQLite thì không → coi là UTC để trình duyệt đổi đúng giờ địa phương."""
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def get_session_or_404(db: Session, session_id: str, user: User | None = None) -> ChatSession:
    """Phiên của người khác trả 404 như không tồn tại (không lộ là có phiên đó)."""
    s = db.get(ChatSession, session_id)
    if s is None or not owns(user, s.user_id):
        raise HTTPException(404, "Không tìm thấy phiên")
    return s


def get_file_or_404(db: Session, file_id: str, user: User | None = None) -> File:
    f = db.get(File, file_id)
    if f is None or not owns(user, f.session.user_id):
        raise HTTPException(404, "Không tìm thấy tệp")
    return f

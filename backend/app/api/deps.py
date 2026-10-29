from typing import Iterator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..db import ChatSession, File, SessionLocal


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_or_404(db: Session, session_id: str) -> ChatSession:
    s = db.get(ChatSession, session_id)
    if s is None:
        raise HTTPException(404, "Không tìm thấy phiên")
    return s


def get_file_or_404(db: Session, file_id: str) -> File:
    f = db.get(File, file_id)
    if f is None:
        raise HTTPException(404, "Không tìm thấy tệp")
    return f

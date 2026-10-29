"""SQLAlchemy models. Schema chi tiết: docs/DATABASE.md."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import get_settings


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    title: Mapped[str] = mapped_column(String(200), default="Phiên mới")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    messages: Mapped[list["Message"]] = relationship(back_populates="session", order_by="Message.seq")
    files: Mapped[list["File"]] = relationship(back_populates="session")


class Message(Base):
    """Một mục trong lịch sử hội thoại.

    `raw` là nội dung gốc của provider (với Gemini: types.Content đã serialize) — phải lưu
    nguyên vẹn vì Gemini 3+ yêu cầu gửi lại thought_signature ở các lượt sau.
    `text` chỉ để hiển thị.
    """

    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))  # user | model | tool
    text: Mapped[str] = mapped_column(Text, default="")
    raw: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class File(Base):
    __tablename__ = "files"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(8))  # xlsx | docx | pptx
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped[ChatSession] = relationship(back_populates="files")
    versions: Mapped[list["FileVersion"]] = relationship(
        back_populates="file", order_by="FileVersion.number", cascade="all, delete-orphan"
    )


class FileVersion(Base):
    __tablename__ = "file_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(64))  # "upload" hoặc tên tool đã tạo ra phiên bản
    summary: Mapped[str] = mapped_column(Text, default="")
    diff: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    file: Mapped[File] = relationship(back_populates="versions")


class ToolCallLog(Base):
    __tablename__ = "tool_calls"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    args: Mapped[dict] = mapped_column(JSON)
    ok: Mapped[bool] = mapped_column(default=True)
    result: Mapped[dict] = mapped_column(JSON)
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


_settings = get_settings()
_settings.storage_dir.mkdir(parents=True, exist_ok=True)
engine = create_engine(_settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)

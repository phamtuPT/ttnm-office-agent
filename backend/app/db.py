"""SQLAlchemy models. Schema chi tiết: docs/DATABASE.md.

Chưa dùng migration: đổi schema thì xoá storage/app.db khi phát triển.
"""
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
    # Bảng ánh xạ ⟦EMAIL_1⟧ → giá trị thật khi bật ẩn danh PII (không bao giờ gửi cho LLM)
    pii_map: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    messages: Mapped[list["Message"]] = relationship(back_populates="session", order_by="Message.seq")
    files: Mapped[list["File"]] = relationship(back_populates="session")


class Turn(Base):
    """Một yêu cầu của người dùng. Gom phiên bản tệp (hoàn tác theo yêu cầu) và đo chỉ số kỹ thuật."""

    __tablename__ = "turns"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    request: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|done|cancelled|error
    provider: Mapped[str] = mapped_column(String(32), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    steps: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    tool_errors: Mapped[int] = mapped_column(Integer, default=0)
    first_token_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Message(Base):
    """Một mục trong lịch sử hội thoại.

    `raw` là nội dung gốc theo định dạng `fmt` của provider (gemini | openai | mock) — phải lưu
    nguyên vẹn vì Gemini 3+ yêu cầu gửi lại thought_signature. Đổi provider giữa phiên thì lịch sử
    khác định dạng được dựng lại từ `text`. `text` là bản hiển thị (đã bỏ ẩn danh).
    """

    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    turn_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))  # user | model | tool
    text: Mapped[str] = mapped_column(Text, default="")
    fmt: Mapped[str] = mapped_column(String(16), default="")
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
    """Một thế hệ sao lưu. Mọi thay đổi trong cùng một yêu cầu (turn) gộp vào một phiên bản."""

    __tablename__ = "file_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    turn_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(255))  # upload | restore | tên các tool, cách nhau dấu phẩy
    summary: Mapped[str] = mapped_column(Text, default="")
    diff: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    file: Mapped[File] = relationship(back_populates="versions")


class ToolCallLog(Base):
    __tablename__ = "tool_calls"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    turn_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    args: Mapped[dict] = mapped_column(JSON)
    ok: Mapped[bool] = mapped_column(default=True)
    result: Mapped[dict] = mapped_column(JSON)
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AppSetting(Base):
    """Cài đặt đổi được lúc đang chạy (nhà cung cấp LLM, model, khoá API, ẩn danh)."""

    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


_settings = get_settings()
_settings.storage_dir.mkdir(parents=True, exist_ok=True)
engine = create_engine(_settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)

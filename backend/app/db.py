"""SQLAlchemy models. Schema chi tiết: docs/DATABASE.md.

CSDL chính là PostgreSQL; SQLite vẫn chạy được để thử nhanh (DATABASE_URL trống).
Đổi schema → sửa model rồi tạo migration: `alembic revision --autogenerate -m "..."` (xem docs/DATABASE.md).
"""
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event, inspect
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import get_settings


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Tài khoản — chỉ dùng khi bật AUTH_ENABLED (máy chủ dùng chung). Người đăng ký đầu tiên là quản trị."""

    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuthToken(Base):
    """Phiên đăng nhập: chỉ lưu SHA-256 của token trong cookie → lộ CSDL cũng không dùng lại được."""

    __tablename__ = "auth_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SusResponse(Base):
    """Phiếu SUS (System Usability Scale) — đánh giá người dùng, đề xuất mục 8.2."""

    __tablename__ = "sus_responses"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    participant: Mapped[str] = mapped_column(String(100), default="")  # mã người tham gia, không cần tên thật
    answers: Mapped[list] = mapped_column(JSON)  # 10 câu, mỗi câu 1–5
    score: Mapped[float] = mapped_column(Float)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", name="fk_chat_sessions_user_id"), nullable=True,
                                                index=True)  # null = chế độ một người
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


log = logging.getLogger(__name__)
MIGRATIONS = Path(__file__).parent / "migrations"
BASELINE = "0001"  # bản migration đầu = schema lúc còn dùng create_all


def database_url(url: str, storage_dir: Path) -> str:
    """Trống → SQLite trong storage. postgres:// / postgresql:// không ghi driver → psycopg 3 (driver duy nhất được cài)."""
    if not url:
        return f"sqlite:///{storage_dir}/app.db"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(url: str) -> Engine:
    if make_url(url).get_backend_name() != "sqlite":
        # pre_ping: bỏ kết nối chết sau khi Postgres khởi động lại thay vì báo lỗi cho người dùng
        return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)
    eng = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _pragmas(conn, _record) -> None:
        # WAL: xem trước đọc được trong lúc agent ghi. foreign_keys: ràng buộc giống Postgres để lỗi lộ ra sớm.
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return eng


_settings = get_settings()
_settings.storage_dir.mkdir(parents=True, exist_ok=True)
engine = make_engine(database_url(_settings.database_url, _settings.storage_dir))
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    """Đưa schema lên migration mới nhất. DB cũ tạo bằng create_all (chưa có bảng alembic_version) → đánh dấu bản đầu."""
    from alembic import command
    from alembic.config import Config

    logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)  # bớt 7 dòng log mỗi lần khởi động
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    try:
        tables = inspect(engine).get_table_names()
    except OperationalError as e:
        raise RuntimeError(
            f"Không kết nối được CSDL {engine.url.render_as_string(hide_password=True)}. "
            "Chạy PostgreSQL bằng `docker compose up -d db` hoặc `python scripts/dev_postgres.py`, "
            "hoặc để trống DATABASE_URL để dùng SQLite."
        ) from e
    if "chat_sessions" in tables and "alembic_version" not in tables:
        log.info("CSDL có sẵn từ trước khi dùng migration → đánh dấu bản %s", BASELINE)
        command.stamp(cfg, BASELINE)
    command.upgrade(cfg, "head")

"""Chép dữ liệu từ CSDL SQLite cũ sang CSDL đang cấu hình trong DATABASE_URL (PostgreSQL).

    python scripts/sqlite_to_postgres.py                      # nguồn mặc định: storage/app.db
    python scripts/sqlite_to_postgres.py duong/dan/app.db

CSDL đích phải còn trống (chưa có phiên nào); schema được tạo bằng migration trước khi chép.
Tệp Office nằm trong storage/<id phiên>/ nên không cần chép — chỉ chép bảng.
"""
import sys
from datetime import timezone
from pathlib import Path

from sqlalchemy import DateTime, create_engine, func, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import Base, ChatSession, SessionLocal, engine, init_db  # noqa: E402


def _clean(value):
    """SQLite lưu giờ không kèm múi giờ (vốn là UTC); Postgres không nhận ký tự NUL trong chuỗi."""
    if isinstance(value, str):
        return value.replace(chr(0), "")
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def main() -> None:
    src_path = Path(sys.argv[1] if len(sys.argv) > 1 else "storage/app.db").resolve()
    if not src_path.exists():
        sys.exit(f"Không thấy {src_path}")
    if engine.dialect.name == "sqlite":
        sys.exit("DATABASE_URL đang trỏ tới SQLite — hãy đặt DATABASE_URL=postgresql://... trong backend/.env")

    init_db()
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(ChatSession)):
            sys.exit("CSDL đích đã có dữ liệu — dừng để không ghi đè.")

    src = create_engine(f"sqlite:///{src_path}")
    with src.connect() as s, engine.begin() as d:
        for table in Base.metadata.sorted_tables:  # bảng cha trước bảng con (khoá ngoại)
            rows = [dict(r._mapping) for r in s.execute(select(table))]
            for row in rows:
                for col in table.columns:
                    v = row.get(col.name)
                    if isinstance(col.type, DateTime) and v is not None and v.tzinfo is None:
                        row[col.name] = v.replace(tzinfo=timezone.utc)
                    else:
                        row[col.name] = _clean(v)
            if rows:
                d.execute(table.insert(), rows)
            print(f"{table.name}: {len(rows)} dòng")
    print(f"Xong. Đích: {engine.url.render_as_string(hide_password=True)}")


if __name__ == "__main__":
    main()

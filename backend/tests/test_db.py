from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.db import Base, database_url, engine


def test_database_url_defaults_and_driver():
    assert database_url("", Path("store")) == f"sqlite:///{Path('store')}/app.db"
    assert database_url("postgres://u:p@h/db", Path(".")) == "postgresql+psycopg://u:p@h/db"
    assert database_url("postgresql://u@h:5432/db", Path(".")) == "postgresql+psycopg://u@h:5432/db"
    assert database_url("postgresql+psycopg://u@h/db", Path(".")) == "postgresql+psycopg://u@h/db"


def test_migrations_match_models():
    """Sửa model trong app/db.py mà quên tạo migration → test này hỏng."""
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []

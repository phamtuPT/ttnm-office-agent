"""Môi trường Alembic: dùng chung engine và model của app nên không cần cấu hình địa chỉ CSDL riêng."""
from logging.config import fileConfig

from alembic import context

from app.db import Base, engine

config = context.config
# Chạy bằng lệnh `alembic` thì lấy cấu hình log từ alembic.ini; backend tự chạy (init_db) thì giữ log của app
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _configure(**kw) -> None:
    context.configure(
        target_metadata=Base.metadata,
        compare_type=True,
        render_as_batch=engine.dialect.name == "sqlite",  # SQLite không ALTER cột được → tạo lại bảng
        **kw,
    )


if context.is_offline_mode():
    _configure(url=engine.url.render_as_string(hide_password=False), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()

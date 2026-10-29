"""Đọc tệp khác trong phiên (làm mẫu thiết kế, nguồn phong cách) từ trong một tool."""
from pathlib import Path

from .registry import ToolCtx, ToolError


def session_file(ctx: ToolCtx, name: str, kind: str) -> Path:
    from ..db import File, SessionLocal  # import muộn: db → tools → db
    from ..versioning import store

    match = next((f for f in ctx.files if f["name"] == name and f["kind"] == kind), None)
    if match is None:
        same_kind = [f["name"] for f in ctx.files if f["kind"] == kind]
        raise ToolError(f"Không có tệp .{kind} '{name}' trong phiên. Tệp .{kind} hiện có: {same_kind}")
    with SessionLocal() as db:
        return store.working_path(db.get(File, match["id"]))

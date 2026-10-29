"""Chạy một lời gọi tool của LLM một cách an toàn.

Thứ tự: tìm tool → kiểm tra tham số → tìm tệp → (hỏi xác nhận nếu phá huỷ) → chạy có timeout
→ nếu là tool ghi: tính diff so với phiên bản hiện tại, lưu phiên bản mới (hoặc rollback khi lỗi).
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import File, ToolCallLog
from ..versioning import diff as difflib_
from ..versioning import store
from .registry import REGISTRY, Selection, ToolCtx, ToolError

ConfirmFn = Callable[[str, dict], Awaitable[bool]]


@dataclass
class ToolResult:
    ok: bool
    data: dict
    file_id: str | None = None
    file_name: str | None = None
    version: int | None = None
    diff: dict | None = None
    summary: str = ""

    def for_model(self) -> dict:
        """Phần trả lại cho LLM — giữ ngắn, không kèm diff chi tiết để tiết kiệm token."""
        if not self.ok:
            return {"ok": False, **self.data}
        out = {"ok": True, **self.data}
        if self.diff is not None:
            out["change_summary"] = self.summary
            if difflib_.is_empty(self.diff):
                out["warning"] = "Tệp không thay đổi gì sau thao tác này"
        return out


class ToolExecutor:
    def __init__(self, db: Session, session_id: str, confirm: ConfirmFn, selection: Selection | None = None):
        self.db = db
        self.session_id = session_id
        self.confirm = confirm
        self.selection = selection

    def _files(self) -> list[File]:
        # Kết nối WS giữ một DB session lâu dài; undo/redo qua REST đổi dữ liệu ở session khác → nạp lại
        self.db.expire_all()
        return self.db.query(File).filter_by(session_id=self.session_id).all()

    async def run(self, name: str, raw_args: dict) -> ToolResult:
        started = time.monotonic()
        result = await self._run(name, raw_args or {})
        self.db.add(ToolCallLog(session_id=self.session_id, name=name, args=raw_args or {}, ok=result.ok,
                                result=result.for_model(), duration_ms=int((time.monotonic() - started) * 1000)))
        self.db.commit()
        return result

    async def _run(self, name: str, raw_args: dict) -> ToolResult:
        tool = REGISTRY.get(name)
        if tool is None:
            return ToolResult(False, {"error": f"Không có tool '{name}'"})
        try:
            args = tool.args_model.model_validate(raw_args)
        except ValidationError as e:
            return ToolResult(False, {"error": f"Tham số không hợp lệ: {e.errors(include_url=False)}"})

        files = self._files()
        f: File | None = None
        if "file" in tool.args_model.model_fields:
            f = next((x for x in files if x.name == args.file), None)
            if f is None:
                return ToolResult(False, {"error": f"Không có tệp '{args.file}'. Tệp hiện có: {[x.name for x in files]}"})
            if tool.kind and f.kind != tool.kind:
                return ToolResult(False, {"error": f"Tool {name} chỉ dùng cho tệp .{tool.kind}"})
            if tool.writes and self.selection and self.selection.file != f.name:
                return ToolResult(False, {"error": f"Người dùng chỉ cho phép sửa tệp '{self.selection.file}'"})

        if tool.destructive and not await self.confirm(name, raw_args):
            return ToolResult(False, {"error": "Người dùng đã từ chối thao tác này"})

        sel = self.selection if (f and self.selection and self.selection.file == f.name) else None
        ctx = ToolCtx(path=store.working_path(f) if f else None, selection=sel,
                      files=[{"name": x.name, "kind": x.kind, "version": x.current_version} for x in files])
        try:
            # Luồng chạy trong thread không huỷ được khi timeout; bản làm việc được rollback bên dưới
            data = await asyncio.wait_for(asyncio.to_thread(tool.handler, args, ctx),
                                          timeout=get_settings().tool_timeout_s)
        except ToolError as e:
            return self._fail(f, tool.writes, str(e))
        except asyncio.TimeoutError:
            return self._fail(f, tool.writes, "Thao tác quá thời gian cho phép")
        except asyncio.CancelledError:  # người dùng bấm Dừng
            self._fail(f, tool.writes, "")
            raise
        except Exception as e:  # lỗi thư viện / tệp hỏng
            return self._fail(f, tool.writes, f"Lỗi khi xử lý tệp: {type(e).__name__}: {e}")

        if not tool.writes or f is None:
            return ToolResult(True, data)
        d = difflib_.compute(f.kind, store.current_snapshot(f), store.working_path(f))
        summary = difflib_.summarize(d)
        version = f.current_version
        if not difflib_.is_empty(d):
            version = store.commit_version(self.db, f, name, summary, d)
        return ToolResult(True, data, f.id, f.name, version, d, summary)

    @staticmethod
    def _fail(f: File | None, writes: bool, msg: str) -> ToolResult:
        if writes and f is not None:
            store.rollback_working(f)
        return ToolResult(False, {"error": msg})

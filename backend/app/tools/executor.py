"""Chạy một lời gọi tool của LLM một cách an toàn.

Thứ tự: tìm tool → kiểm tra tham số → tìm tệp, kiểm tra loại tệp và vùng chọn → (hỏi xác nhận nếu phá huỷ)
→ tool ghi/tạo chạy trên TỆP TẠM, có timeout → thành công: os.replace (ghi nguyên tử) + sao lưu phiên bản;
lỗi/timeout/huỷ: bỏ tệp tạm, bản làm việc không bị đụng tới.
"""
import asyncio
import inspect
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import File, ToolCallLog
from ..versioning import diff as difflib_
from ..versioning import store
from .registry import REGISTRY, Selection, Tool, ToolCtx, ToolError

ConfirmFn = Callable[[str, dict], Awaitable[bool]]


@dataclass
class FileChange:
    file_id: str
    file_name: str
    version: int
    summary: str
    diff: dict


@dataclass
class ToolResult:
    ok: bool
    data: dict
    changes: list[FileChange] = field(default_factory=list)
    images: list[tuple[bytes, str]] = field(default_factory=list)
    unchanged: bool = False  # tool ghi chạy xong nhưng tệp không khác gì

    def for_model(self) -> dict:
        """Phần trả lại cho LLM — giữ ngắn, không kèm diff chi tiết để tiết kiệm token."""
        if not self.ok:
            return {"ok": False, **self.data}
        out = {"ok": True, **self.data}
        if self.changes:
            out["changes"] = [f"{c.file_name} → phiên bản {c.version}: {c.summary}" for c in self.changes]
        if self.unchanged:
            out["warning"] = "Tệp không thay đổi gì sau thao tác này"
        if self.images:
            out["images_attached"] = len(self.images)
        return out


class ToolExecutor:
    def __init__(self, db: Session, session_id: str, confirm: ConfirmFn, selection: Selection | None = None,
                 turn_id: str | None = None):
        self.db = db
        self.session_id = session_id
        self.confirm = confirm
        # Ô đơn chỉ là điểm neo cho prompt, không phải giới hạn → không áp các kiểm tra phạm vi
        self.selection = None if selection is not None and selection.is_anchor else selection
        self.turn_id = turn_id

    def _files(self) -> list[File]:
        # Kết nối WS giữ một DB session lâu dài; undo/redo qua REST đổi dữ liệu ở session khác → nạp lại
        self.db.expire_all()
        return self.db.query(File).filter_by(session_id=self.session_id).all()

    async def run(self, name: str, raw_args: dict) -> ToolResult:
        started = time.monotonic()
        result = await self._run(name, raw_args or {})
        self.db.add(ToolCallLog(session_id=self.session_id, turn_id=self.turn_id, name=name[:64], args=raw_args or {},
                                ok=result.ok, result=result.for_model(),
                                duration_ms=int((time.monotonic() - started) * 1000)))
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
        file_arg = getattr(args, "file", None)
        if tool.creates:
            if store.kind_of(file_arg) != tool.kind:
                return ToolResult(False, {"error": f"Tên tệp phải có đuôi .{tool.kind}"})
            if store.safe_filename(file_arg) != file_arg:
                return ToolResult(False, {"error": f"Tên tệp không hợp lệ, gợi ý: {store.safe_filename(file_arg)}"})
            if any(x.name == file_arg for x in files):
                return ToolResult(False, {"error": f"Đã có tệp '{file_arg}', hãy chọn tên khác hoặc sửa tệp đó"})
        elif file_arg is not None:
            f = next((x for x in files if x.name == file_arg), None)
            if f is None:
                return ToolResult(False, {"error": f"Không có tệp '{file_arg}'. Tệp hiện có: {[x.name for x in files]}"})
            if tool.kind and f.kind != tool.kind:
                return ToolResult(False, {"error": f"Tool {name} chỉ dùng cho tệp .{tool.kind}"})
            if tool.writes and self.selection and self.selection.file != f.name:
                return ToolResult(False, {"error": f"Người dùng chỉ cho phép sửa tệp '{self.selection.file}'"})

        if tool.destructive and not await self.confirm(name, raw_args):
            return ToolResult(False, {"error": "Người dùng đã từ chối thao tác này"})

        tmp: Path | None = None
        if tool.creates:
            tmp = store.scratch_path(self.session_id, tool.kind)
        elif tool.writes and f is not None:
            tmp = store.scratch_path(self.session_id, f.kind)
            shutil.copy2(store.working_path(f), tmp)
        path = tmp or (store.working_path(f) if f else None)

        sel = self.selection if (f and self.selection and self.selection.file == f.name) else None
        ctx = ToolCtx(path=path, selection=sel,
                      files=[{"id": x.id, "name": x.name, "kind": x.kind, "version": x.current_version} for x in files],
                      assets_dir=store.assets_dir(self.session_id), session_id=self.session_id,
                      turn_id=self.turn_id, db=self.db if tool.inline else None)
        try:
            data = await self._call(tool, args, ctx)
        except ToolError as e:
            return self._fail(tmp, str(e))
        except asyncio.TimeoutError:
            return self._fail(tmp, "Thao tác quá thời gian cho phép")
        except asyncio.CancelledError:  # người dùng bấm Dừng
            self._fail(tmp, "")
            raise
        except Exception as e:  # lỗi thư viện / tệp hỏng
            return self._fail(tmp, f"Lỗi khi xử lý tệp: {type(e).__name__}: {e}")

        images = data.pop("_images", [])
        changes = data.pop("_changes", [])
        if tool.creates:
            nf = store.create_file(self.db, self.session_id, file_arg, tmp.read_bytes(), source=name,
                                   turn_id=self.turn_id, rename_if_exists=False)
            tmp.unlink(missing_ok=True)
            changes = [FileChange(nf.id, nf.name, 1, "Tạo tệp mới", {"created": True})]
        elif tool.writes and f is not None:
            step_diff = difflib_.compute(f.kind, store.working_path(f), tmp)
            if difflib_.is_empty(step_diff):
                tmp.unlink(missing_ok=True)
                return ToolResult(True, data, images=images, unchanged=True)
            version, d, summary = store.apply_change(self.db, f, tmp, name, self.turn_id)
            changes = [FileChange(f.id, f.name, version, summary, d)]
        return ToolResult(True, data, changes=changes, images=images)

    async def _call(self, tool: Tool, args, ctx: ToolCtx) -> dict:
        if inspect.iscoroutinefunction(tool.handler):  # tool gọi dịch vụ ngoài (sandbox) — không chặn event loop
            return await asyncio.wait_for(tool.handler(args, ctx), timeout=get_settings().tool_timeout_s + 30)
        if tool.inline:
            return tool.handler(args, ctx)
        # Thread không huỷ được khi timeout, nhưng nó chỉ ghi vào tệp tạm → bản làm việc an toàn
        return await asyncio.wait_for(asyncio.to_thread(tool.handler, args, ctx),
                                      timeout=get_settings().tool_timeout_s)

    @staticmethod
    def _fail(tmp: Path | None, msg: str) -> ToolResult:
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass  # Windows: thread timeout có thể còn giữ tệp; tệp .tmp-* bị bỏ qua ở mọi nơi
        return ToolResult(False, {"error": msg})

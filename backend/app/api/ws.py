"""WebSocket chat. Giao thức sự kiện: docs/API.md."""
import asyncio
import base64
import binascii
import json
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from .. import runtime_settings
from ..agent.loop import StepLimitError, TurnStats, run_turn
from ..agent.prompts import context_block, system_prompt
from ..config import get_settings
from ..db import ChatSession, File, Message, SessionLocal, Turn
from ..llm import get_provider
from ..llm.base import HistoryRow, LLMError
from ..privacy.pii import Anonymizer
from ..tools.assets import list_assets, normalize_image, save_asset
from ..tools.executor import ToolExecutor
from ..tools.registry import Selection
from ..versioning import store

log = logging.getLogger(__name__)
router = APIRouter()

IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/heic", "image/gif"}
CONFIRM_TIMEOUT_S = 120


@router.websocket("/ws/sessions/{session_id}")
async def chat_ws(ws: WebSocket, session_id: str):
    db = SessionLocal()
    try:
        if db.get(ChatSession, session_id) is None:
            await ws.close(code=4404)
            return
        await ws.accept()
        await Connection(ws, db, session_id).serve()
    finally:
        db.close()


class Connection:
    def __init__(self, ws: WebSocket, db, session_id: str):
        self.ws, self.db, self.session_id = ws, db, session_id
        self.settings = get_settings()
        self.turn: asyncio.Task | None = None
        self.confirms: dict[str, asyncio.Future] = {}
        self.send_lock = asyncio.Lock()

    async def send(self, event: dict) -> None:
        try:
            async with self.send_lock:
                await self.ws.send_json(event)
        except (WebSocketDisconnect, RuntimeError):
            pass  # client đã ngắt — lượt vẫn chạy xong và được lưu

    async def serve(self) -> None:
        try:
            while True:
                try:
                    msg = json.loads(await self.ws.receive_text())
                except json.JSONDecodeError:
                    await self.send({"type": "error", "message": "Tin nhắn không phải JSON"})
                    continue
                kind = msg.get("type")
                if kind == "chat":
                    if self.turn and not self.turn.done():
                        await self.send({"type": "error", "message": "Đang xử lý yêu cầu trước, hãy đợi hoặc bấm Dừng"})
                    else:
                        self.turn = asyncio.create_task(self.handle_chat(msg))
                elif kind == "confirm.response":
                    fut = self.confirms.get(msg.get("id"))
                    if fut and not fut.done():
                        fut.set_result(bool(msg.get("approved")))
                elif kind == "cancel":
                    if self.turn and not self.turn.done():
                        self.turn.cancel()
                else:
                    await self.send({"type": "error", "message": f"Không hiểu loại tin nhắn '{kind}'"})
        except WebSocketDisconnect:
            for fut in self.confirms.values():
                if not fut.done():
                    fut.set_result(False)
            if self.turn and not self.turn.done():
                await self.turn  # để lượt chạy xong và lưu lịch sử

    async def confirm(self, tool_name: str, args: dict) -> bool:
        cid = uuid.uuid4().hex
        fut = asyncio.get_running_loop().create_future()
        self.confirms[cid] = fut
        await self.send({"type": "confirm.request", "id": cid, "tool": tool_name, "args": args})
        try:
            return await asyncio.wait_for(fut, CONFIRM_TIMEOUT_S)
        except asyncio.TimeoutError:
            return False
        finally:
            self.confirms.pop(cid, None)

    def _parse_images(self, items: list) -> list[tuple[bytes, str]]:
        out = []
        for it in items or []:
            if it.get("mime") not in IMAGE_MIMES:
                raise ValueError("Chỉ nhận ảnh PNG, JPEG, WEBP, HEIC, GIF")
            try:
                data = base64.b64decode(it.get("data", ""), validate=True)
            except binascii.Error:
                raise ValueError("Ảnh không hợp lệ")
            if len(data) > self.settings.max_image_mb * 1024 * 1024:
                raise ValueError(f"Mỗi ảnh tối đa {self.settings.max_image_mb} MB")
            out.append(normalize_image(data))
        return out

    async def handle_chat(self, msg: dict) -> None:
        text = (msg.get("text") or "").strip()
        try:
            images = self._parse_images(msg.get("images"))
            selection = Selection.model_validate(msg["selection"]) if msg.get("selection") else None
        except (ValueError, ValidationError) as e:
            await self.send({"type": "error", "message": str(e)})
            return
        if not text and not images:
            await self.send({"type": "error", "message": "Tin nhắn trống"})
            return

        self.db.expire_all()  # nạp lại dữ liệu có thể đã đổi qua REST (tải tệp, undo, cài đặt, ...)
        cfg = runtime_settings.load(self.db)
        try:
            provider = get_provider(cfg)
        except LLMError as e:
            await self.send({"type": "error", "message": str(e)})
            return

        session = self.db.get(ChatSession, self.session_id)
        files = [{"name": f.name, "kind": f.kind, "version": f.current_version}
                 for f in self.db.query(File).filter_by(session_id=self.session_id)]
        active_file = msg.get("active_file") if any(f["name"] == msg.get("active_file") for f in files) else None
        adir = store.assets_dir(self.session_id)
        new_assets = [save_asset(adir, data, mime) for data, mime in images]

        pii = Anonymizer(session.pii_map) if cfg.pii_masking and cfg.provider != "mock" else None
        ctx = context_block(files, selection.model_dump(exclude_none=True) if selection else None,
                            active_file, list_assets(adir), new_assets)
        user_text = f"{ctx}\n\n{text}"
        user_raw = provider.user_message(pii.mask_text(user_text) if pii else user_text, images)
        rows = [HistoryRow(m.role, m.text, m.fmt, m.raw) for m in session.messages]
        history = provider.adopt_history(rows)

        turn = Turn(session_id=self.session_id, request=text, provider=provider.name, model=provider.model)
        self.db.add(turn)
        self.db.commit()
        executor = ToolExecutor(self.db, self.session_id, self.confirm, selection, turn.id)
        stats = TurnStats()
        out: list[tuple[str, str, dict]] = []
        note = None
        await self.send({"type": "turn.start", "turn_id": turn.id, "provider": provider.name, "model": provider.model})
        try:
            async with asyncio.timeout(self.settings.turn_timeout_s):
                await run_turn(provider=provider, executor=executor, history=history, user_raw=user_raw,
                               system=system_prompt(text, files, active_file), emit=self.send,
                               max_steps=self.settings.max_steps, out=out, pii=pii, stats=stats)
            turn.status = "done"
        except asyncio.CancelledError:
            note, turn.status = "(Người dùng đã dừng lượt này.)", "cancelled"
            await self.send({"type": "turn.cancelled"})
        except TimeoutError:
            note, turn.status = "(Lượt này bị dừng vì quá thời gian xử lý.)", "error"
            await self.send({"type": "error", "message": "Quá thời gian xử lý, hãy thử chia nhỏ yêu cầu"})
        except (StepLimitError, LLMError) as e:
            note, turn.status = f"({e})", "error"
            await self.send({"type": "error", "message": str(e)})
        except Exception:
            log.exception("Lỗi khi xử lý lượt chat")
            note, turn.status = "(Lỗi hệ thống khi xử lý lượt này.)", "error"
            await self.send({"type": "error", "message": "Lỗi hệ thống, vui lòng thử lại"})

        if note:
            turn.error = note
            if not (out and out[-1][0] == "model"):
                out.append(("model", note, provider.model_text_message(note)))
        seq = len(session.messages)
        for i, (role, t, raw) in enumerate([("user", text, user_raw), *out]):
            self.db.add(Message(session_id=self.session_id, turn_id=turn.id, seq=seq + i, role=role, text=t,
                                fmt=provider.fmt, raw=raw))
        if pii:
            session.pii_map = dict(pii.mapping)
        turn.steps, turn.tool_calls, turn.tool_errors = stats.steps, stats.tool_calls, stats.tool_errors
        turn.first_token_ms = stats.first_token_ms
        turn.duration_ms = int((time.monotonic() - stats.started) * 1000)
        turn.input_tokens, turn.output_tokens = stats.input_tokens, stats.output_tokens
        self.db.commit()
        await self.send({"type": "turn.end", "turn_id": turn.id})

        if session.title == "Phiên mới" and text:
            await self._name_session(provider, session, text, pii)

    async def _name_session(self, provider, session: ChatSession, text: str, pii: Anonymizer | None) -> None:
        try:
            title = await provider.quick(
                "Đặt tiêu đề ngắn (tối đa 6 từ, tiếng Việt) cho cuộc trò chuyện bắt đầu bằng câu dưới. "
                f"Chỉ trả về tiêu đề.\n{pii.mask_text(text) if pii else text}")
            title = pii.unmask_text(title) if pii else title
        except Exception:
            title = text[:40]
        session.title = title.strip().strip('"')[:200] or text[:40]
        self.db.commit()
        await self.send({"type": "session.title", "title": session.title})

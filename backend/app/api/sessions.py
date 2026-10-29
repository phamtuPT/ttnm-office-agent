import shutil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import runtime_settings
from ..db import ChatSession, File, FileVersion, Message, ToolCallLog, Turn
from ..llm import get_provider
from ..llm.base import LLMError
from ..tools.assets import list_assets
from ..versioning import blank, store
from .deps import get_db, get_session_or_404, iso
from .files import file_out

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

MAX_AUDIO_MB = 10


def _session_out(s: ChatSession, updated_at=None, message_count: int = 0) -> dict:
    files = [{"id": f.id, "name": f.name, "kind": f.kind} for f in s.files]
    # Tệp làm ảnh xem trước: tệp có phiên bản hiện tại mới nhất (tệp vừa được sửa/tạo)
    primary = max(s.files, key=lambda f: max((v.created_at for v in f.versions if v.number == f.current_version),
                                             default=f.created_at), default=None)
    preview = {"file_id": primary.id, "version": primary.current_version, "kind": primary.kind} if primary else None
    return {"id": s.id, "title": s.title, "created_at": iso(s.created_at),
            "updated_at": iso(updated_at or s.created_at), "kind": primary.kind if primary else None,
            "files": files, "message_count": message_count, "preview": preview}


class CreateSession(BaseModel):
    kind: Literal["xlsx", "docx", "pptx"] | None = Field(
        None, description="Bắt đầu với một tệp trống loại này; bỏ trống = phiên không có tệp (để tải tệp lên)")


@router.post("")
def create_session(body: CreateSession | None = None, db: Session = Depends(get_db)):
    kind = body.kind if body else None
    s = ChatSession(title=blank.DEFAULTS[kind][1] if kind else "Phiên mới")
    db.add(s)
    db.commit()
    if kind:
        store.create_file(db, s.id, blank.DEFAULTS[kind][0], blank.blank_bytes(kind), source="blank")
        db.refresh(s)
    return _session_out(s)


@router.get("")
def list_sessions(db: Session = Depends(get_db)):
    """Phiên gần đây (mở/sửa gần nhất trước) cho trang chủ."""
    last_msg = dict(db.query(Message.session_id, func.max(Message.created_at)).group_by(Message.session_id).all())
    counts = dict(db.query(Message.session_id, func.count(Message.id))
                  .filter(Message.role == "user").group_by(Message.session_id).all())
    last_ver = dict(db.query(File.session_id, func.max(FileVersion.created_at))
                    .join(FileVersion, FileVersion.file_id == File.id).group_by(File.session_id).all())
    out = []
    for s in db.query(ChatSession).all():
        updated = max([t for t in (s.created_at, last_msg.get(s.id), last_ver.get(s.id)) if t is not None])
        out.append(_session_out(s, updated, counts.get(s.id, 0)))
    return sorted(out, key=lambda x: x["updated_at"], reverse=True)


@router.get("/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    return _session_out(get_session_or_404(db, session_id))


class RenameSession(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@router.patch("/{session_id}")
def rename_session(session_id: str, body: RenameSession, db: Session = Depends(get_db)):
    s = get_session_or_404(db, session_id)
    s.title = body.title.strip() or s.title
    db.commit()
    return _session_out(s)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Xoá phiên cùng toàn bộ tệp, phiên bản, ảnh và lịch sử hội thoại. Không hoàn tác được."""
    s = get_session_or_404(db, session_id)
    for model in (Message, Turn, ToolCallLog):
        db.query(model).filter_by(session_id=session_id).delete()
    for f in list(s.files):
        db.delete(f)  # kéo theo file_versions (cascade)
    db.delete(s)
    db.commit()
    shutil.rmtree(store.session_dir(session_id), ignore_errors=True)


@router.get("/{session_id}/messages")
def list_messages(session_id: str, db: Session = Depends(get_db)):
    """Lịch sử để hiển thị: chỉ tin nhắn có chữ của người dùng và model."""
    s = get_session_or_404(db, session_id)
    return [{"id": m.id, "role": m.role, "text": m.text, "turn_id": m.turn_id, "created_at": iso(m.created_at)}
            for m in s.messages if m.role in ("user", "model") and m.text]


@router.post("/{session_id}/undo-last")
def undo_last_request(session_id: str, db: Session = Depends(get_db)):
    """Hoàn tác mọi thay đổi tệp của yêu cầu gần nhất (một nhấp)."""
    get_session_or_404(db, session_id)
    files = store.undo_turn(db, session_id)
    if not files:
        raise HTTPException(409, "Không có yêu cầu nào đã sửa tệp để hoàn tác")
    return [file_out(f) for f in files]


@router.get("/{session_id}/turns")
def list_turns(session_id: str, db: Session = Depends(get_db)):
    """Chỉ số kỹ thuật từng yêu cầu (độ trễ, số bước, token, lỗi) — phục vụ đánh giá mục 8.3."""
    get_session_or_404(db, session_id)
    turns = db.query(Turn).filter_by(session_id=session_id).order_by(Turn.created_at)
    return [{c.name: (iso(v) if c.name == "created_at" else v) for c in Turn.__table__.columns
             for v in [getattr(t, c.name)]} for t in turns]


@router.get("/{session_id}/assets")
def assets(session_id: str, db: Session = Depends(get_db)):
    get_session_or_404(db, session_id)
    return list_assets(store.assets_dir(session_id))


@router.get("/{session_id}/assets/{name}")
def asset(session_id: str, name: str, db: Session = Depends(get_db)):
    get_session_or_404(db, session_id)
    if name not in list_assets(store.assets_dir(session_id)):
        raise HTTPException(404, "Không có ảnh này")
    return FileResponse(store.assets_dir(session_id) / name)


@router.post("/{session_id}/transcribe")
async def transcribe(session_id: str, audio: UploadFile, db: Session = Depends(get_db)):
    """Giọng nói → văn bản (dự phòng khi trình duyệt không có Web Speech API).
    Frontend hiển thị văn bản cho người dùng sửa, KHÔNG tự gửi."""
    get_session_or_404(db, session_id)
    data = await audio.read()
    if len(data) > MAX_AUDIO_MB * 1024 * 1024:
        raise HTTPException(413, f"Ghi âm vượt quá {MAX_AUDIO_MB} MB")
    mime = (audio.content_type or "audio/webm").split(";")[0]
    try:
        return {"text": await get_provider(runtime_settings.load(db)).transcribe(data, mime)}
    except LLMError as e:
        raise HTTPException(502, str(e))

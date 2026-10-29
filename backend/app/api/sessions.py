from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import runtime_settings
from ..db import ChatSession, Turn
from ..llm import get_provider
from ..llm.base import LLMError
from ..tools.assets import list_assets
from ..versioning import store
from .deps import get_db, get_session_or_404, iso
from .files import file_out

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

MAX_AUDIO_MB = 10


def _session_out(s: ChatSession) -> dict:
    return {"id": s.id, "title": s.title, "created_at": iso(s.created_at)}


@router.post("")
def create_session(db: Session = Depends(get_db)):
    s = ChatSession()
    db.add(s)
    db.commit()
    return _session_out(s)


@router.get("")
def list_sessions(db: Session = Depends(get_db)):
    return [_session_out(s) for s in db.query(ChatSession).order_by(ChatSession.created_at.desc())]


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

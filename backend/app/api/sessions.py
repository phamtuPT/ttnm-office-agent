from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import ChatSession
from ..llm import get_provider
from ..llm.base import LLMError
from .deps import get_db, get_session_or_404

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

MAX_AUDIO_MB = 10


def _session_out(s: ChatSession) -> dict:
    return {"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()}


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
    return [{"id": m.id, "role": m.role, "text": m.text, "created_at": m.created_at.isoformat()}
            for m in s.messages if m.role in ("user", "model") and m.text]


@router.post("/{session_id}/transcribe")
async def transcribe(session_id: str, audio: UploadFile, db: Session = Depends(get_db)):
    """Giọng nói → văn bản. Frontend hiển thị văn bản cho người dùng sửa trước khi gửi."""
    get_session_or_404(db, session_id)
    data = await audio.read()
    if len(data) > MAX_AUDIO_MB * 1024 * 1024:
        raise HTTPException(413, f"Ghi âm vượt quá {MAX_AUDIO_MB} MB")
    mime = (audio.content_type or "audio/webm").split(";")[0]
    try:
        return {"text": await get_provider().transcribe(data, mime)}
    except LLMError as e:
        raise HTTPException(502, str(e))

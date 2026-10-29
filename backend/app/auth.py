"""Tài khoản và phiên đăng nhập (chỉ khi AUTH_ENABLED — máy chủ dùng chung cho nhiều người).

Tắt (mặc định, chạy trên máy một người): mọi API như cũ, current_user trả None, không lọc theo người dùng.
Bật: cookie HttpOnly "oa_session" chứa token ngẫu nhiên; CSDL chỉ lưu SHA-256 của token. Mật khẩu băm bằng scrypt
(thư viện chuẩn, có muối). Mỗi người chỉ thấy phiên/tệp của mình; người đăng ký đầu tiên là quản trị viên
(đổi cài đặt AI, xem kết quả SUS).
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, WebSocket
from sqlalchemy.orm import Session

from .config import get_settings
from .db import AuthToken, SessionLocal, User

COOKIE = "oa_session"
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, n, r, p, salt, digest = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, base64.b64decode(digest))


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_token(db: Session, user: User) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(AuthToken(token_hash=_hash_token(raw), user_id=user.id,
                     expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().session_days)))
    db.commit()
    return raw


def revoke_token(db: Session, raw: str | None) -> None:
    if raw:
        db.query(AuthToken).filter_by(token_hash=_hash_token(raw)).delete()
        db.commit()


def user_for_token(db: Session, raw: str | None) -> User | None:
    if not raw:
        return None
    tok = db.get(AuthToken, _hash_token(raw))
    if tok is None:
        return None
    expires = tok.expires_at if tok.expires_at.tzinfo else tok.expires_at.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        db.delete(tok)
        db.commit()
        return None
    return db.get(User, tok.user_id)


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(request: Request, db: Session = Depends(_db)) -> User | None:
    """None = chế độ một người (không bật đăng nhập). Bật đăng nhập mà chưa đăng nhập → 401."""
    if not get_settings().auth_enabled:
        return None
    user = user_for_token(db, request.cookies.get(COOKIE))
    if user is None:
        raise HTTPException(401, "Cần đăng nhập")
    return user


def require_admin(user: User | None = Depends(current_user)) -> User | None:
    if user is not None and not user.is_admin:
        raise HTTPException(403, "Chỉ quản trị viên được làm thao tác này")
    return user


def websocket_user(ws: WebSocket, db: Session) -> tuple[bool, User | None]:
    """(được phép, người dùng) cho kết nối WebSocket — trình duyệt tự gửi cookie khi bắt tay."""
    if not get_settings().auth_enabled:
        return True, None
    user = user_for_token(db, ws.cookies.get(COOKIE))
    return user is not None, user


def owns(user: User | None, owner_id: str | None) -> bool:
    return user is None or owner_id == user.id

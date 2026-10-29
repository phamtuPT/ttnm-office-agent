import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import COOKIE, current_user, hash_password, issue_token, revoke_token, user_for_token, verify_password
from ..config import get_settings
from ..db import User
from .deps import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Register(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: str = Field("", max_length=100)
    password: str = Field(min_length=8, max_length=200)


class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name or u.email.split("@")[0], "is_admin": u.is_admin}


def _login(resp: Response, db: Session, user: User) -> dict:
    s = get_settings()
    resp.set_cookie(COOKIE, issue_token(db, user), max_age=s.session_days * 86400, httponly=True, samesite="lax",
                    secure=s.cookie_secure, path="/")
    return user_out(user)


def _require_enabled() -> None:
    if not get_settings().auth_enabled:
        raise HTTPException(404, "Ứng dụng đang chạy chế độ một người dùng, không cần đăng nhập")


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    """Giao diện hỏi lúc khởi động: có bật đăng nhập không, ai đang đăng nhập."""
    s = get_settings()
    if not s.auth_enabled:
        return {"enabled": False, "user": None, "can_register": False}
    user = user_for_token(db, request.cookies.get(COOKIE))
    return {"enabled": True, "user": user_out(user) if user else None,
            "can_register": s.auth_open_registration or db.query(User).count() == 0}


@router.post("/register")
def register(body: Register, resp: Response, db: Session = Depends(get_db)):
    _require_enabled()
    first = db.query(User).count() == 0
    if not first and not get_settings().auth_open_registration:
        raise HTTPException(403, "Máy chủ đã tắt đăng ký — nhờ quản trị viên tạo tài khoản")
    email = body.email.strip().lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "Email này đã có tài khoản")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password), is_admin=first)
    db.add(user)
    db.commit()
    return _login(resp, db, user)


@router.post("/login")
async def login(body: Login, resp: Response, db: Session = Depends(get_db)):
    _require_enabled()
    user = db.query(User).filter_by(email=body.email.strip().lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        await asyncio.sleep(0.5)  # làm chậm đoán mật khẩu; cùng thông báo cho email sai và mật khẩu sai
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    return _login(resp, db, user)


@router.post("/logout", status_code=204)
def logout(request: Request, resp: Response, db: Session = Depends(get_db), _user=Depends(current_user)):
    revoke_token(db, request.cookies.get(COOKIE))
    resp.delete_cookie(COOKIE, path="/")

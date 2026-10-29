from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import runtime_settings
from ..auth import current_user, require_admin
from ..preview import render
from .deps import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings_view(db: Session = Depends(get_db), _user=Depends(current_user)):
    data = runtime_settings.public_view(runtime_settings.load(db))
    data["render_available"] = render.available()
    return data


@router.put("")
def update_settings(patch: runtime_settings.SettingsPatch, db: Session = Depends(get_db),
                    _admin=Depends(require_admin)):  # khoá API, nhà cung cấp: dùng chung cả máy chủ
    """Đổi nhà cung cấp/model/khoá API — có hiệu lực từ yêu cầu chat kế tiếp, không cần khởi động lại.
    Khoá API chỉ ghi, không bao giờ được trả về."""
    try:
        cfg = runtime_settings.save(db, patch)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return runtime_settings.public_view(cfg)

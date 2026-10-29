"""Ảnh người dùng gửi kèm trong chat: chuẩn hoá bằng Pillow, lưu vào storage/<session>/assets để tool chèn vào tài liệu."""
import io
from pathlib import Path

from PIL import Image, ImageOps

from .registry import ToolCtx, ToolError

MAX_SIDE = 2048


def normalize_image(data: bytes) -> tuple[bytes, str]:
    """Xoay theo EXIF, thu nhỏ cạnh dài về MAX_SIDE, nén lại. Trả về (bytes, mime)."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise ValueError("Không đọc được ảnh")
    img = ImageOps.exif_transpose(img)
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    if img.mode in ("RGBA", "LA", "P"):
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue(), "image/png"
    img.convert("RGB").save(buf, "JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


def save_asset(folder: Path, data: bytes, mime: str) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    ext = "png" if mime == "image/png" else "jpg"
    n = len(list(folder.glob("anh-*"))) + 1
    name = f"anh-{n}.{ext}"
    (folder / name).write_bytes(data)
    return name


def list_assets(folder: Path) -> list[str]:
    return sorted((p.name for p in folder.glob("anh-*")), key=lambda n: int(n.split("-")[1].split(".")[0])) \
        if folder.exists() else []


def asset_path(ctx: ToolCtx, name: str) -> Path:
    p = (ctx.assets_dir / Path(name).name) if ctx.assets_dir else None
    if p is None or not p.is_file():
        raise ToolError(f"Không có ảnh '{name}'. Ảnh hiện có: {list_assets(ctx.assets_dir) if ctx.assets_dir else []}")
    return p

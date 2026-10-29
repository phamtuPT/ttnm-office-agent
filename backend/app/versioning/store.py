"""Lưu trữ tệp và phiên bản.

storage/<session_id>/files/<tên tệp>              bản làm việc (tool đọc/ghi trực tiếp)
storage/<session_id>/versions/<file_id>/v<n>.ext   bản chụp sau mỗi lần ghi, v1 = bản tải lên

Undo/redo chỉ là chép một bản chụp đè lên bản làm việc rồi đổi File.current_version.
Ghi mới sau khi undo sẽ xoá các phiên bản phía sau (giống undo trong trình soạn thảo).
"""
import re
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import File, FileVersion

ALLOWED_KINDS = {"xlsx", "docx", "pptx"}
_SAFE_NAME = re.compile(r"[^\w.\- ]", re.UNICODE)


def safe_filename(name: str) -> str:
    name = Path(name).name  # bỏ mọi thành phần thư mục → chặn path traversal
    name = _SAFE_NAME.sub("_", name).strip(" .")
    return name[:200] or "file"


def session_dir(session_id: str) -> Path:
    return get_settings().storage_dir / session_id


def working_path(f: File) -> Path:
    return session_dir(f.session_id) / "files" / f.name


def version_path(f: File, number: int) -> Path:
    return session_dir(f.session_id) / "versions" / f.id / f"v{number}.{f.kind}"


def create_file(db: Session, session_id: str, name: str, data: bytes) -> File:
    name = safe_filename(name)
    kind = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"Chỉ hỗ trợ tệp {', '.join(sorted(ALLOWED_KINDS))}")
    stem, ext = name.rsplit(".", 1)
    i = 1
    while db.query(File).filter_by(session_id=session_id, name=name).first():
        i += 1
        name = f"{stem} ({i}).{ext}"

    f = File(session_id=session_id, name=name, kind=kind, current_version=1)
    db.add(f)
    db.flush()
    wp = working_path(f)
    wp.parent.mkdir(parents=True, exist_ok=True)
    wp.write_bytes(data)
    _snapshot(f, 1)
    f.versions.append(FileVersion(number=1, source="upload", summary="Bản tải lên"))
    db.commit()
    return f


def _snapshot(f: File, number: int) -> None:
    vp = version_path(f, number)
    vp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(working_path(f), vp)


def commit_version(db: Session, f: File, source: str, summary: str, diff: dict) -> int:
    """Gọi sau khi tool ghi thành công: chụp bản làm việc thành phiên bản mới."""
    for v in [v for v in f.versions if v.number > f.current_version]:
        version_path(f, v.number).unlink(missing_ok=True)
        f.versions.remove(v)
    number = f.current_version + 1
    _snapshot(f, number)
    f.versions.append(FileVersion(number=number, source=source, summary=summary, diff=diff))
    f.current_version = number
    db.commit()
    return number


def rollback_working(f: File) -> None:
    """Tool lỗi giữa chừng → trả bản làm việc về phiên bản hiện tại."""
    shutil.copy2(version_path(f, f.current_version), working_path(f))


def current_snapshot(f: File) -> Path:
    return version_path(f, f.current_version)


def restore(db: Session, f: File, number: int) -> None:
    if not any(v.number == number for v in f.versions):
        raise ValueError("Không có phiên bản này")
    shutil.copy2(version_path(f, number), working_path(f))
    f.current_version = number
    db.commit()


def undo(db: Session, f: File) -> None:
    if f.current_version <= 1:
        raise ValueError("Không còn thay đổi nào để hoàn tác")
    restore(db, f, f.current_version - 1)


def redo(db: Session, f: File) -> None:
    if f.current_version >= max(v.number for v in f.versions):
        raise ValueError("Không còn thay đổi nào để làm lại")
    restore(db, f, f.current_version + 1)

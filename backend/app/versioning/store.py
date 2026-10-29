"""Lưu trữ tệp, sao lưu và hoàn tác.

storage/<session_id>/files/<tên tệp>              bản làm việc (workspace)
storage/<session_id>/versions/<file_id>/v<n>.ext   các thế hệ sao lưu (.history), v1 = bản tải lên/tạo mới
storage/<session_id>/assets/                       ảnh người dùng gửi kèm

- Mọi thay đổi trong CÙNG MỘT yêu cầu gộp vào một phiên bản → hoàn tác một nhấp hoàn tác cả yêu cầu.
- Hoàn tác/làm lại chỉ dời con trỏ `current_version`; ghi mới khi đang ở bản cũ sẽ xoá các bản phía sau.
- Khôi phục từ lịch sử tạo PHIÊN BẢN MỚI (chép nội dung bản cũ) → lần khôi phục cũng hoàn tác được.
- Chỉ giữ `max_generations` thế hệ gần nhất.
"""
import os
import re
import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import File, FileVersion
from . import diff as difflib_

ALLOWED_KINDS = {"xlsx", "docx", "pptx"}
_SAFE_NAME = re.compile(r"[^\w.\- ()]", re.UNICODE)


def safe_filename(name: str) -> str:
    name = Path(name).name  # bỏ mọi thành phần thư mục → chặn path traversal
    name = _SAFE_NAME.sub("_", name).strip(" .")
    return name[:200] or "file"


def kind_of(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def session_dir(session_id: str) -> Path:
    return get_settings().storage_dir / session_id


def assets_dir(session_id: str) -> Path:
    return session_dir(session_id) / "assets"


def working_path(f: File) -> Path:
    return session_dir(f.session_id) / "files" / f.name


def version_path(f: File, number: int) -> Path:
    return session_dir(f.session_id) / "versions" / f.id / f"v{number}.{f.kind}"


def scratch_path(session_id: str, kind: str) -> Path:
    """Tệp tạm cạnh bản làm việc: tool ghi vào đây, thành công mới os.replace → ghi nguyên tử."""
    p = session_dir(session_id) / "files" / f".tmp-{uuid.uuid4().hex}.{kind}"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def unique_name(db: Session, session_id: str, name: str) -> str:
    stem, ext = name.rsplit(".", 1)
    i, candidate = 1, name
    while db.query(File).filter_by(session_id=session_id, name=candidate).first():
        i += 1
        candidate = f"{stem} ({i}).{ext}"
    return candidate


def create_file(db: Session, session_id: str, name: str, data: bytes, *, source: str = "upload",
                turn_id: str | None = None, rename_if_exists: bool = True) -> File:
    name = safe_filename(name)
    kind = kind_of(name)
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"Chỉ hỗ trợ tệp {', '.join(sorted(ALLOWED_KINDS))}")
    if rename_if_exists:
        name = unique_name(db, session_id, name)
    elif db.query(File).filter_by(session_id=session_id, name=name).first():
        raise ValueError(f"Đã có tệp '{name}'")

    f = File(session_id=session_id, name=name, kind=kind, current_version=1)
    db.add(f)
    db.flush()
    wp = working_path(f)
    wp.parent.mkdir(parents=True, exist_ok=True)
    wp.write_bytes(data)
    _snapshot(f, 1)
    summary = "Bản tải lên" if source == "upload" else "Tạo tệp mới"
    f.versions.append(FileVersion(number=1, turn_id=turn_id, source=source, summary=summary,
                                  diff={"created": True}))
    db.commit()
    return f


def _snapshot(f: File, number: int) -> None:
    vp = version_path(f, number)
    vp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(working_path(f), vp)


def _current(f: File) -> FileVersion:
    return next(v for v in f.versions if v.number == f.current_version)


def current_snapshot(f: File) -> Path:
    return version_path(f, f.current_version)


def apply_change(db: Session, f: File, new_content: Path, source: str, turn_id: str | None) -> tuple[int, dict, str]:
    """Đưa tệp tạm `new_content` thành bản làm việc và ghi phiên bản. Trả về (số phiên bản, diff gộp, tóm tắt).

    Cùng turn với phiên bản hiện tại (và đó là bản mới nhất) → ghi đè phiên bản đó, diff tính từ bản trước turn.
    """
    os.replace(new_content, working_path(f))  # nguyên tử trên cùng ổ đĩa
    cur = _current(f)
    latest = max(v.number for v in f.versions)
    same_turn = turn_id is not None and cur.turn_id == turn_id and cur.number == latest and cur.source != "upload"

    if same_turn:
        _snapshot(f, cur.number)
        base = _previous(f, cur.number)
        d = (difflib_.compute(f.kind, version_path(f, base.number), working_path(f)) if base
             else {"created": True})
        cur.diff, cur.summary = d, difflib_.summarize(d)
        if source not in cur.source.split(","):
            cur.source = f"{cur.source},{source}"[:255]
        db.commit()
        return cur.number, d, cur.summary

    for v in [v for v in f.versions if v.number > f.current_version]:
        version_path(f, v.number).unlink(missing_ok=True)
        f.versions.remove(v)
    number = f.current_version + 1  # bản hiện tại giờ là bản mới nhất
    _snapshot(f, number)
    d = difflib_.compute(f.kind, version_path(f, f.current_version), working_path(f))
    summary = difflib_.summarize(d)
    f.versions.append(FileVersion(number=number, turn_id=turn_id, source=source, summary=summary, diff=d))
    f.current_version = number
    _prune(f)
    db.commit()
    return number, d, summary


def _previous(f: File, number: int) -> FileVersion | None:
    older = [v for v in f.versions if v.number < number]
    return older[-1] if older else None


def _next(f: File, number: int) -> FileVersion | None:
    newer = [v for v in f.versions if v.number > number]
    return newer[0] if newer else None


def _prune(f: File) -> None:
    keep = get_settings().max_generations
    extra = [v for v in f.versions if v.number != f.current_version][: max(0, len(f.versions) - keep)]
    for v in extra:
        version_path(f, v.number).unlink(missing_ok=True)
        f.versions.remove(v)


def _move_to(db: Session, f: File, number: int) -> None:
    shutil.copy2(version_path(f, number), working_path(f))
    f.current_version = number
    db.commit()


def undo(db: Session, f: File) -> None:
    prev = _previous(f, f.current_version)
    if prev is None:
        raise ValueError("Không còn thay đổi nào để hoàn tác")
    _move_to(db, f, prev.number)


def redo(db: Session, f: File) -> None:
    nxt = _next(f, f.current_version)
    if nxt is None:
        raise ValueError("Không còn thay đổi nào để làm lại")
    _move_to(db, f, nxt.number)


def restore(db: Session, f: File, number: int) -> int:
    """Khôi phục nội dung phiên bản `number` thành một phiên bản MỚI (hoàn tác được)."""
    if not any(v.number == number for v in f.versions):
        raise ValueError("Không có phiên bản này (có thể đã bị xoá do vượt số thế hệ lưu giữ)")
    if number == f.current_version:
        raise ValueError("Đây đã là phiên bản hiện tại")
    tmp = scratch_path(f.session_id, f.kind)
    shutil.copy2(version_path(f, number), tmp)
    new_number, _, _ = apply_change(db, f, tmp, "restore", None)
    v = _current(f)
    v.summary = f"Khôi phục phiên bản {number}"
    db.commit()
    return new_number


def undo_turn(db: Session, session_id: str, exclude_turn: str | None = None) -> list[File]:
    """Hoàn tác yêu cầu gần nhất đã sửa tệp (trên mọi tệp nó đã sửa). Trả về các tệp đã hoàn tác."""
    files = db.query(File).filter_by(session_id=session_id).all()
    candidates = [(_current(f), f) for f in files]
    candidates = [(v, f) for v, f in candidates if v.turn_id and v.turn_id != exclude_turn and v.source != "upload"]
    if not candidates:
        return []
    last_turn = max(candidates, key=lambda vf: vf[0].created_at)[0].turn_id
    undone = []
    for v, f in candidates:
        if v.turn_id == last_turn and _previous(f, v.number):
            undo(db, f)
            undone.append(f)
    return undone

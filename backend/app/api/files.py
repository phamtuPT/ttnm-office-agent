import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import File, Turn
from ..preview import render, thumbnail
from ..tools.registry import REGISTRY, ToolCtx
from ..tools.word import document_equations
from ..versioning import store
from .deps import get_db, get_file_or_404, get_session_or_404, iso

router = APIRouter(prefix="/api", tags=["files"])

MIME = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
OUTLINE_TOOL = {"xlsx": "excel_inspect", "docx": "word_inspect", "pptx": "pptx_inspect"}
MAX_UNCOMPRESSED = 200 * 1024 * 1024


def file_out(f: File) -> dict:
    numbers = [v.number for v in f.versions] or [1]
    return {"id": f.id, "name": f.name, "kind": f.kind, "current_version": f.current_version,
            "oldest_version": min(numbers), "latest_version": max(numbers)}


def _validate_office_zip(data: bytes) -> None:
    """Tệp Office là zip: chặn tệp hỏng, tệp chứa macro và zip bomb."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
            if any(n.lower().endswith("vbaproject.bin") for n in names):
                raise HTTPException(400, "Không nhận tệp có macro")
            if sum(i.file_size for i in z.infolist()) > MAX_UNCOMPRESSED:
                raise HTTPException(400, "Tệp giải nén quá lớn")
            if "[Content_Types].xml" not in names:
                raise HTTPException(400, "Tệp không phải định dạng Office hợp lệ")
    except zipfile.BadZipFile:
        raise HTTPException(400, "Tệp bị hỏng hoặc không phải định dạng Office hợp lệ")


@router.post("/sessions/{session_id}/files")
async def upload_file(session_id: str, file: UploadFile, db: Session = Depends(get_db)):
    get_session_or_404(db, session_id)
    limit = get_settings().max_upload_mb
    data = await file.read(limit * 1024 * 1024 + 1)
    if len(data) > limit * 1024 * 1024:
        raise HTTPException(413, f"Tệp vượt quá {limit} MB")
    _validate_office_zip(data)
    try:
        f = store.create_file(db, session_id, file.filename or "file", data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return file_out(f)


@router.get("/sessions/{session_id}/files")
def list_files(session_id: str, db: Session = Depends(get_db)):
    return [file_out(f) for f in get_session_or_404(db, session_id).files]


@router.get("/files/{file_id}/content")
def file_content(file_id: str, db: Session = Depends(get_db)):
    f = get_file_or_404(db, file_id)
    return FileResponse(store.working_path(f), media_type=MIME[f.kind], filename=f.name,
                        headers={"Cache-Control": "no-store"})


@router.get("/files/{file_id}/outline")
def file_outline(file_id: str, db: Session = Depends(get_db)):
    """Dàn ý (sheet / đoạn văn / slide) để frontend hiển thị và cho người dùng chọn vùng."""
    f = get_file_or_404(db, file_id)
    tool = REGISTRY[OUTLINE_TOOL[f.kind]]
    args = tool.args_model(file=f.name, **({"limit": 10_000} if f.kind == "docx" else {}))
    return tool.handler(args, ToolCtx(path=store.working_path(f), selection=None))


@router.get("/files/{file_id}/equations")
def file_equations(file_id: str, db: Session = Depends(get_db)):
    """Công thức toán trong tài liệu Word (LaTeX, theo thứ tự) — bản in dùng để vẽ lại công thức bằng KaTeX."""
    f = get_file_or_404(db, file_id)
    return document_equations(store.working_path(f)) if f.kind == "docx" else []


@router.get("/files/{file_id}/thumbnail.png")
def file_thumbnail(file_id: str, db: Session = Depends(get_db)):
    """Ảnh thu nhỏ trang/slide/bảng đầu tiên của phiên bản hiện tại (URL kèm ?v=<phiên bản> để trình duyệt cache)."""
    f = get_file_or_404(db, file_id)
    cache = store.session_dir(f.session_id) / "thumbs" / f"{f.id}-v{f.current_version}.png"
    try:
        png = thumbnail.build(store.current_snapshot(f), f.kind, cache)
    except Exception as e:  # tệp hỏng/lạ: giao diện tự dùng ảnh minh hoạ thay thế
        raise HTTPException(422, f"Không tạo được ảnh xem trước: {type(e).__name__}")
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})


def _render_dir(f: File):
    return store.session_dir(f.session_id) / "renders" / f.id / f"v{f.current_version}"


@router.get("/files/{file_id}/pages")
def file_pages(file_id: str, db: Session = Depends(get_db)):
    """Ảnh từng trang/slide (LibreOffice). available=false nếu máy chưa cài LibreOffice → giao diện dùng dàn ý."""
    f = get_file_or_404(db, file_id)
    if f.kind == "xlsx" or not render.available():
        return {"available": False, "pages": 0}
    try:
        pages = render.render(store.working_path(f), _render_dir(f))
    except render.RenderError as e:
        raise HTTPException(500, str(e))
    return {"available": True, "pages": len(pages), "version": f.current_version}


@router.get("/files/{file_id}/pages/{index}.png")
def file_page_png(file_id: str, index: int, db: Session = Depends(get_db)):
    f = get_file_or_404(db, file_id)
    p = _render_dir(f) / f"page-{index}.png"
    if not p.exists():
        raise HTTPException(404, "Chưa render trang này — gọi /pages trước")
    return FileResponse(p, media_type="image/png")


@router.get("/files/{file_id}/versions")
def list_versions(file_id: str, db: Session = Depends(get_db)):
    """Lịch sử phiên bản, mỗi phiên bản ứng với một yêu cầu (kèm câu yêu cầu để người dùng nhận ra)."""
    f = get_file_or_404(db, file_id)
    requests = {t.id: t.request for t in db.query(Turn).filter(Turn.id.in_([v.turn_id for v in f.versions if v.turn_id]))}
    return [{"number": v.number, "source": v.source, "summary": v.summary, "diff": v.diff,
             "request": requests.get(v.turn_id, ""), "created_at": iso(v.created_at),
             "current": v.number == f.current_version}
            for v in reversed(f.versions)]


@router.post("/files/{file_id}/undo")
def undo(file_id: str, db: Session = Depends(get_db)):
    f = get_file_or_404(db, file_id)
    try:
        store.undo(db, f)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return file_out(f)


@router.post("/files/{file_id}/redo")
def redo(file_id: str, db: Session = Depends(get_db)):
    f = get_file_or_404(db, file_id)
    try:
        store.redo(db, f)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return file_out(f)


@router.post("/files/{file_id}/restore/{number}")
def restore(file_id: str, number: int, db: Session = Depends(get_db)):
    """Khôi phục nội dung phiên bản cũ thành phiên bản MỚI → lần khôi phục cũng hoàn tác được."""
    f = get_file_or_404(db, file_id)
    try:
        store.restore(db, f, number)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return file_out(f)

"""Tool hệ thống: tự kiểm tra bằng thị giác, hoàn tác theo lời nói."""
from pydantic import BaseModel, Field

from ..preview import render as render_svc
from ..versioning import store
from .executor import FileChange
from .registry import ToolCtx, ToolError, tool

MAX_PAGES = 6


class NoArgs(BaseModel):
    pass


@tool("list_files", "Liệt kê các tệp trong phiên (kể cả tệp agent đã tạo).", NoArgs)
def list_files(args: NoArgs, ctx: ToolCtx) -> dict:
    return {"files": ctx.files}


class RenderArgs(BaseModel):
    file: str = Field(description="Tên tệp .docx hoặc .pptx")
    pages: list[int] | None = Field(None, description=f"Chỉ số trang/slide cần xem (từ 0), tối đa {MAX_PAGES}. "
                                                      "Bỏ trống = các trang đầu")


@tool("render_pages", "Chụp ảnh trang Word / slide PowerPoint vừa làm để TỰ KIỂM TRA bằng mắt: chữ tràn khung, "
      "hình chồng lấn, bố cục lệch. Gọi sau khi tạo/sửa slide; thấy lỗi thì sửa rồi kiểm tra lại.", RenderArgs)
def render_pages(args: RenderArgs, ctx: ToolCtx) -> dict:
    if ctx.path is None or ctx.path.suffix.lower() not in (".docx", ".pptx"):
        raise ToolError("Chỉ render được tệp .docx và .pptx")
    if not render_svc.available():
        return {"available": False, "note": "Máy chủ chưa cài LibreOffice — bỏ qua bước tự kiểm tra bằng hình ảnh"}
    f = next(x for x in ctx.files if x["name"] == args.file)
    cache = store.session_dir(ctx.session_id) / "renders" / f["id"] / f"v{f['version']}"
    try:
        pages = render_svc.render(ctx.path, cache)
    except render_svc.RenderError as e:
        raise ToolError(str(e))
    wanted = args.pages or list(range(min(len(pages), MAX_PAGES)))
    bad = [i for i in wanted if not 0 <= i < len(pages)]
    if bad:
        raise ToolError(f"Trang {bad} không tồn tại (có {len(pages)} trang)")
    return {"total_pages": len(pages), "shown": wanted[:MAX_PAGES],
            "_images": [(pages[i].read_bytes(), "image/png") for i in wanted[:MAX_PAGES]]}


@tool("undo_last_request", "Hoàn tác MỌI thay đổi tệp của yêu cầu gần nhất trước yêu cầu này (khi người dùng nói "
      "'hoàn tác', 'quay lại như cũ'...). Người dùng có thể bấm Làm lại.", NoArgs, inline=True)
def undo_last_request(args: NoArgs, ctx: ToolCtx) -> dict:
    files = store.undo_turn(ctx.db, ctx.session_id, exclude_turn=ctx.turn_id)
    if not files:
        raise ToolError("Không có yêu cầu nào trước đó đã sửa tệp để hoàn tác")
    changes = [FileChange(f.id, f.name, f.current_version, f"Hoàn tác về phiên bản {f.current_version}", {})
               for f in files]
    return {"undone": [f.name for f in files], "_changes": changes}


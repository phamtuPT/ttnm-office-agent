"""Tool hệ thống: tự kiểm tra bằng thị giác, hoàn tác theo lời nói, so sánh, ảnh, OCR, phân tích dữ liệu."""
import base64
import io

import httpx
from PIL import Image
from pydantic import BaseModel, Field

from ..config import get_settings
from ..media import ocr
from ..preview import render as render_svc
from ..versioning import diff, store
from .assets import asset_path, normalize_image, save_asset
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



# ---------- So sánh ----------

class CompareVersionsArgs(BaseModel):
    file: str
    from_version: int = Field(description="Phiên bản cũ")
    to_version: int | None = Field(None, description="Phiên bản mới; bỏ trống = phiên bản hiện tại")


@tool("compare_versions", "So sánh hai phiên bản của cùng một tệp (xem đã đổi gì) để tóm tắt khác biệt.",
      CompareVersionsArgs)
def compare_versions(args: CompareVersionsArgs, ctx: ToolCtx) -> dict:
    f = next(x for x in ctx.files if x["name"] == args.file)
    to = args.to_version or f["version"]
    a = store.version_path_for(ctx.session_id, f["id"], f["kind"], args.from_version)
    b = store.version_path_for(ctx.session_id, f["id"], f["kind"], to)
    if not a.exists() or not b.exists():
        raise ToolError("Không có phiên bản này (có thể đã bị xoá do vượt số thế hệ lưu giữ)")
    d = diff.compute(f["kind"], a, b)
    return {"from": args.from_version, "to": to, "summary": diff.summarize(d), "diff": _trim(d)}


class CompareFilesArgs(BaseModel):
    file: str = Field(description="Tệp thứ nhất (bản cũ)")
    other: str = Field(description="Tệp thứ hai cùng loại (bản mới)")


@tool("compare_files", "So sánh hai tệp cùng loại (ví dụ hai bản hợp đồng) và trả về các khác biệt.", CompareFilesArgs)
def compare_files(args: CompareFilesArgs, ctx: ToolCtx) -> dict:
    a = next(x for x in ctx.files if x["name"] == args.file)
    b = next((x for x in ctx.files if x["name"] == args.other), None)
    if b is None:
        raise ToolError(f"Không có tệp '{args.other}'")
    if a["kind"] != b["kind"]:
        raise ToolError("Chỉ so sánh được hai tệp cùng loại")
    pa = store.version_path_for(ctx.session_id, a["id"], a["kind"], a["version"])
    pb = store.version_path_for(ctx.session_id, b["id"], b["kind"], b["version"])
    d = diff.compute(a["kind"], pa, pb)
    return {"summary": diff.summarize(d), "diff": _trim(d)}


def _trim(d: dict, limit: int = 40) -> dict:
    return {k: (v[:limit] if isinstance(v, list) else v) for k, v in d.items()}


# ---------- Ảnh ----------

class ImageEditArgs(BaseModel):
    image: str = Field(description="Tên ảnh, xem [Ảnh đính kèm]")
    rotate: int = Field(0, description="Xoay theo chiều kim đồng hồ: 0, 90, 180, 270")
    crop: list[float] | None = Field(None, description="Vùng giữ lại [trái, trên, phải, dưới] theo tỉ lệ 0..1")
    max_width: int | None = Field(None, description="Thu nhỏ về chiều rộng tối đa (px)")
    grayscale: bool = False


@tool("image_edit", "Xử lý ảnh người dùng gửi trước khi chèn vào tài liệu: xoay, cắt, thu nhỏ, chuyển trắng đen. "
      "Tạo ảnh MỚI, ảnh gốc giữ nguyên.", ImageEditArgs)
def image_edit(args: ImageEditArgs, ctx: ToolCtx) -> dict:
    src = asset_path(ctx, args.image)
    img = Image.open(src)
    if args.rotate % 360:
        img = img.rotate(-args.rotate, expand=True)
    if args.crop:
        c = args.crop
        if len(c) != 4 or not all(0 <= v <= 1 for v in c) or c[0] >= c[2] or c[1] >= c[3]:
            raise ToolError("crop phải là [trái, trên, phải, dưới] trong khoảng 0..1, trái < phải, trên < dưới")
        w, h = img.size
        img = img.crop((int(c[0] * w), int(c[1] * h), int(c[2] * w), int(c[3] * h)))
    if args.max_width and img.width > args.max_width:
        img = img.resize((args.max_width, round(img.height * args.max_width / img.width)))
    if args.grayscale:
        img = img.convert("L")
    buf = io.BytesIO()
    png = img.mode in ("RGBA", "LA", "P")
    (img if png else img.convert("RGB")).save(buf, "PNG" if png else "JPEG", quality=88)
    name = save_asset(ctx.assets_dir, buf.getvalue(), "image/png" if png else "image/jpeg")
    return {"created_image": name, "size": list(img.size)}


class OcrArgs(BaseModel):
    image: str = Field(description="Tên ảnh, xem [Ảnh đính kèm]")


@tool("ocr_image", "Nhận dạng chữ trong ảnh bằng OCR cục bộ (Tesseract) — dùng để đối chiếu khi ảnh mờ hoặc "
      "người dùng không muốn gửi ảnh lên đám mây.", OcrArgs)
def ocr_image(args: OcrArgs, ctx: ToolCtx) -> dict:
    src = asset_path(ctx, args.image)
    if not ocr.available():
        return {"available": False, "note": "Máy chủ chưa cài Tesseract OCR"}
    try:
        return {"available": True, "text": ocr.ocr(src)[:8000]}
    except RuntimeError as e:
        raise ToolError(str(e))


# ---------- Phân tích dữ liệu trong sandbox ----------

MAX_TEXT_OUT = 6000
_transport = None  # test thay bằng httpx.MockTransport


class RunPythonArgs(BaseModel):
    code: str = Field(description="Mã Python. Có sẵn pandas, numpy, scipy, statsmodels, seaborn, matplotlib, "
                                  "openpyxl. Tệp đầu vào nằm ở thư mục hiện tại. Lưu hình bằng plt.savefig('ten.png'), "
                                  "bảng bằng df.to_csv/to_excel. In kết quả cần đọc bằng print().")
    files: list[str] = Field(default_factory=list, description="Tên tệp trong phiên cần đưa vào (đọc bằng tên đó)")


@tool("run_python", "Chạy mã Python phân tích dữ liệu (thống kê, hồi quy, ANOVA, ARIMA, vẽ hình) trong sandbox "
      "cách ly không có mạng. Người dùng xem mã và xác nhận trước khi chạy. Hình .png trả về thành ảnh để chèn "
      "vào Word/PowerPoint; tệp .xlsx/.docx/.pptx trả về thành tệp mới trong phiên.", RunPythonArgs,
      destructive=True, inline=True)
async def run_python(args: RunPythonArgs, ctx: ToolCtx) -> dict:
    s = get_settings()
    if not s.sandbox_url:
        raise ToolError("Chưa bật sandbox chạy Python (SANDBOX_URL). Hãy phân tích bằng công thức Excel thay thế")
    inputs = {}
    for name in args.files:
        f = next((x for x in ctx.files if x["name"] == name), None)
        if f is None:
            raise ToolError(f"Không có tệp '{name}'")
        p = store.version_path_for(ctx.session_id, f["id"], f["kind"], f["version"])
        inputs[name] = base64.b64encode(p.read_bytes()).decode()
    try:
        async with httpx.AsyncClient(base_url=s.sandbox_url, transport=_transport,
                                     timeout=s.sandbox_timeout_s + 15) as client:
            r = await client.post("/run", json={"code": args.code, "files": inputs, "timeout": s.sandbox_timeout_s})
            r.raise_for_status()
            res = r.json()
    except httpx.HTTPError as e:
        raise ToolError(f"Không gọi được sandbox: {e}")

    out = {"exit_code": res["exit_code"], "stdout": res["stdout"][-MAX_TEXT_OUT:],
           "stderr": res["stderr"][-2000:], "outputs": []}
    images, changes = [], []
    for name, b64 in res.get("outputs", {}).items():
        data = base64.b64decode(b64)
        ext = name.rsplit(".", 1)[-1].lower()
        if ext in ("png", "jpg", "jpeg"):
            img, mime = normalize_image(data)
            asset = save_asset(ctx.assets_dir, img, mime)
            out["outputs"].append({"file": name, "saved_as_image": asset})
            images.append((img, mime))
        elif ext in ("xlsx", "docx", "pptx"):
            nf = store.create_file(ctx.db, ctx.session_id, name, data, source="run_python", turn_id=ctx.turn_id)
            out["outputs"].append({"file": name, "saved_as": nf.name})
            changes.append(FileChange(nf.id, nf.name, 1, "Tạo tệp mới từ phân tích", {"created": True}))
        elif ext in ("csv", "txt", "json", "md"):
            out["outputs"].append({"file": name, "content": data.decode("utf-8", "ignore")[:MAX_TEXT_OUT]})
    return {**out, "_images": images[:4], "_changes": changes}

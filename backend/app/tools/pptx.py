"""Tool PowerPoint (python-pptx). TV2 mở rộng: xoá/sắp xếp slide, bảng, biểu đồ, mẫu thiết kế, ..."""
from typing import Literal

from pptx import Presentation
from pptx.util import Cm, Emu
from pydantic import BaseModel, Field

from .assets import asset_path
from .registry import ToolCtx, ToolError, tool

FILE = Field(description="Tên tệp .pptx trong phiên")
SLIDE_16_9 = (Emu(12192000), Emu(6858000))


def _slide(prs, index: int):
    if not 0 <= index < len(prs.slides):
        raise ToolError(f"Slide {index} không tồn tại (có {len(prs.slides)} slide, đánh số từ 0)")
    return prs.slides[index]


def _check_selection(ctx: ToolCtx, index: int) -> None:
    sel = ctx.selection
    if sel and sel.slides is not None and index not in sel.slides:
        raise ToolError(f"Slide {index} nằm ngoài các slide người dùng chọn {sel.slides}")


class InspectArgs(BaseModel):
    file: str = FILE


@tool("pptx_inspect", "Xem dàn ý bài trình chiếu: từng slide với layout, các shape có chữ (kèm chỉ số) và "
      "ghi chú thuyết trình. Luôn gọi trước khi sửa.", InspectArgs, kind="pptx")
def pptx_inspect(args: InspectArgs, ctx: ToolCtx) -> dict:
    prs = Presentation(ctx.path)
    slides = []
    for i, s in enumerate(prs.slides):
        shapes = [{"index": j, "name": sh.name, "text": sh.text_frame.text[:300]}
                  for j, sh in enumerate(s.shapes) if sh.has_text_frame]
        notes = s.notes_slide.notes_text_frame.text[:300] if s.has_notes_slide else ""
        slides.append({"index": i, "layout": s.slide_layout.name, "shapes": shapes, "notes": notes})
    return {"slide_size_cm": [round(prs.slide_width / 360000, 1), round(prs.slide_height / 360000, 1)],
            "slides": slides}


class SlideSpec(BaseModel):
    layout: Literal["title", "title_content", "section", "title_only", "blank"] = "title_content"
    title: str = ""
    bullets: list[str] = Field(default_factory=list, description="Các ý, mỗi ý ngắn gọn (≤ 12 từ)")
    notes: str = Field("", description="Ghi chú thuyết trình")


_LAYOUTS = {"title": 0, "title_content": 1, "section": 2, "title_only": 5, "blank": 6}


class CreateArgs(BaseModel):
    file: str = Field(description="Tên tệp mới, đuôi .pptx")
    slides: list[SlideSpec]


@tool("pptx_create_presentation", "Tạo bài trình chiếu 16:9 mới. Sau khi tạo nên gọi render_pages để tự kiểm tra "
      "chữ tràn/chồng lấn.", CreateArgs, kind="pptx", creates=True)
def pptx_create_presentation(args: CreateArgs, ctx: ToolCtx) -> dict:
    # TODO(TV2): dùng mẫu thiết kế (default_theme.pptx) thay cho mẫu trắng mặc định của python-pptx
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_16_9
    for spec in args.slides:
        s = prs.slides.add_slide(prs.slide_layouts[_LAYOUTS[spec.layout]])
        if s.shapes.title is not None and spec.title:
            s.shapes.title.text = spec.title
        if spec.bullets:
            body = next((ph for ph in s.placeholders if ph.placeholder_format.idx == 1), None)
            if body is None:
                raise ToolError(f"Layout '{spec.layout}' không có ô nội dung, dùng 'title_content'")
            body.text_frame.text = spec.bullets[0]
            for b in spec.bullets[1:]:
                body.text_frame.add_paragraph().text = b
        if spec.notes:
            s.notes_slide.notes_text_frame.text = spec.notes
    prs.save(ctx.path)
    return {"created": args.file, "slides": len(args.slides)}


class SetTextArgs(BaseModel):
    file: str = FILE
    slide: int = Field(description="Chỉ số slide (từ 0)")
    shape: int = Field(description="Chỉ số shape trong slide, lấy từ pptx_inspect")
    text: str = Field(description="Nội dung mới; xuống dòng bằng \\n để tạo nhiều đoạn")


@tool("pptx_set_text", "Thay nội dung chữ của một shape, giữ định dạng của đoạn đầu.", SetTextArgs,
      kind="pptx", writes=True)
def pptx_set_text(args: SetTextArgs, ctx: ToolCtx) -> dict:
    _check_selection(ctx, args.slide)
    prs = Presentation(ctx.path)
    shapes = list(_slide(prs, args.slide).shapes)
    if not 0 <= args.shape < len(shapes) or not shapes[args.shape].has_text_frame:
        raise ToolError(f"Shape {args.shape} không tồn tại hoặc không chứa chữ")
    tf = shapes[args.shape].text_frame
    lines = args.text.split("\n")
    first = tf.paragraphs[0]
    for p in list(tf.paragraphs)[1:]:
        p._p.getparent().remove(p._p)
    if first.runs:
        first.runs[0].text = lines[0]
        for r in first.runs[1:]:
            r._r.getparent().remove(r._r)
    else:
        first.text = lines[0]
    for line in lines[1:]:
        tf.add_paragraph().text = line
    prs.save(ctx.path)
    return {"slide": args.slide, "shape": args.shape}


class NotesArgs(BaseModel):
    file: str = FILE
    slide: int = Field(description="Chỉ số slide (từ 0)")
    notes: str


@tool("pptx_set_notes", "Ghi chú thuyết trình cho một slide (thay toàn bộ ghi chú cũ).", NotesArgs,
      kind="pptx", writes=True)
def pptx_set_notes(args: NotesArgs, ctx: ToolCtx) -> dict:
    _check_selection(ctx, args.slide)
    prs = Presentation(ctx.path)
    _slide(prs, args.slide).notes_slide.notes_text_frame.text = args.notes
    prs.save(ctx.path)
    return {"slide": args.slide}


class AddImageArgs(BaseModel):
    file: str = FILE
    slide: int = Field(description="Chỉ số slide (từ 0)")
    image: str = Field(description="Tên ảnh người dùng đã gửi, xem [Ảnh đính kèm]")
    left_cm: float = 2
    top_cm: float = 4
    width_cm: float = Field(12, description="Chiều rộng (cm); slide 16:9 rộng 33,9 cm")


@tool("pptx_add_image", "Chèn ảnh người dùng đã gửi vào một slide.", AddImageArgs, kind="pptx", writes=True)
def pptx_add_image(args: AddImageArgs, ctx: ToolCtx) -> dict:
    img = asset_path(ctx, args.image)
    _check_selection(ctx, args.slide)
    prs = Presentation(ctx.path)
    _slide(prs, args.slide).shapes.add_picture(str(img), Cm(args.left_cm), Cm(args.top_cm), width=Cm(args.width_cm))
    prs.save(ctx.path)
    return {"slide": args.slide, "image": args.image}

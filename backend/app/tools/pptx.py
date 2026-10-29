"""Tool PowerPoint (python-pptx). TV2 mở rộng ở giai đoạn 4: thêm/xoá/sắp xếp slide, chèn ảnh, bảng, ..."""
from pptx import Presentation
from pydantic import BaseModel, Field

from .registry import ToolCtx, ToolError, tool

FILE = Field(description="Tên tệp .pptx trong phiên")


class InspectArgs(BaseModel):
    file: str = FILE


@tool("pptx_inspect", "Xem dàn ý bài trình chiếu: từng slide với layout và các shape có chữ (kèm chỉ số). "
      "Luôn gọi trước khi sửa.", InspectArgs, kind="pptx")
def pptx_inspect(args: InspectArgs, ctx: ToolCtx) -> dict:
    prs = Presentation(ctx.path)
    slides = []
    for i, s in enumerate(prs.slides):
        shapes = [{"index": j, "name": sh.name, "text": sh.text_frame.text[:300]}
                  for j, sh in enumerate(s.shapes) if sh.has_text_frame]
        slides.append({"index": i, "layout": s.slide_layout.name, "shapes": shapes})
    return {"slides": slides}


class SetTextArgs(BaseModel):
    file: str = FILE
    slide: int = Field(description="Chỉ số slide (từ 0)")
    shape: int = Field(description="Chỉ số shape trong slide, lấy từ pptx_inspect")
    text: str = Field(description="Nội dung mới; xuống dòng bằng \\n để tạo nhiều đoạn")


@tool("pptx_set_text", "Thay nội dung chữ của một shape, giữ định dạng của đoạn đầu.", SetTextArgs,
      kind="pptx", writes=True)
def pptx_set_text(args: SetTextArgs, ctx: ToolCtx) -> dict:
    sel = ctx.selection
    if sel and sel.slides is not None and args.slide not in sel.slides:
        raise ToolError(f"Slide {args.slide} nằm ngoài các slide người dùng chọn {sel.slides}")
    prs = Presentation(ctx.path)
    if not 0 <= args.slide < len(prs.slides):
        raise ToolError(f"Slide {args.slide} không tồn tại (có {len(prs.slides)} slide)")
    shapes = list(prs.slides[args.slide].shapes)
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

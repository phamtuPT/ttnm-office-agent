"""Tool PowerPoint (python-pptx). TV2 mở rộng: xoá/sắp xếp slide, bảng, biểu đồ, mẫu thiết kế, ..."""
from typing import Literal

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.util import Cm, Emu, Pt
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
    theme: Literal["clean", "midnight", "warm"] = Field(
        "clean", description="clean = nền trắng chữ xanh đậm; midnight = nền xanh đêm chữ sáng; "
                             "warm = nền kem, tiêu đề cam san hô")


# (nền, màu tiêu đề, màu chữ) — tương phản đủ để đọc trên máy chiếu
THEMES = {
    "clean": ("FFFFFF", "16324F", "2E3A46"),
    "midnight": ("0F1923", "FFB830", "F0EDE6"),
    "warm": ("FBF6EE", "E0533A", "3A2E26"),
}


def _apply_theme(slide, theme: str) -> None:
    bg, title_c, body_c = THEMES[theme]
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor.from_string(bg)
    for sh in slide.placeholders:
        if not sh.has_text_frame:
            continue
        is_title = sh.placeholder_format.idx == 0
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor.from_string(title_c if is_title else body_c)
                if is_title:
                    r.font.bold = True


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
        _apply_theme(s, args.theme)
    prs.save(ctx.path)
    return {"created": args.file, "slides": len(args.slides), "theme": args.theme}


class TextItem(BaseModel):
    slide: int = Field(description="Chỉ số slide (từ 0)")
    shape: int = Field(description="Chỉ số shape trong slide, lấy từ pptx_inspect")
    text: str = Field(description="Nội dung mới; xuống dòng bằng \\n để tạo nhiều đoạn")


class SetTextArgs(BaseModel):
    file: str = FILE
    items: list[TextItem] = Field(description="Các shape cần sửa — gộp TẤT CẢ thay đổi chữ vào một lần gọi")


@tool("pptx_set_text", "Thay nội dung chữ của các shape (có thể trên nhiều slide), giữ định dạng của đoạn đầu.",
      SetTextArgs, kind="pptx", writes=True)
def pptx_set_text(args: SetTextArgs, ctx: ToolCtx) -> dict:
    if not args.items:
        raise ToolError("Cần ít nhất một mục cần sửa")
    for it in args.items:
        _check_selection(ctx, it.slide)
    prs = Presentation(ctx.path)
    for it in args.items:
        _set_text(prs, it)
    prs.save(ctx.path)
    return {"updated": [[it.slide, it.shape] for it in args.items]}


def _set_text(prs, it: TextItem) -> None:
    shapes = list(_slide(prs, it.slide).shapes)
    if not 0 <= it.shape < len(shapes) or not shapes[it.shape].has_text_frame:
        raise ToolError(f"Slide {it.slide}: shape {it.shape} không tồn tại hoặc không chứa chữ")
    tf = shapes[it.shape].text_frame
    lines = it.text.split("\n")
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


class AddSlideArgs(BaseModel):
    file: str = FILE
    after: int = Field(description="Chèn sau slide này (từ 0); -1 để chèn lên đầu")
    slide: SlideSpec


def _move_slide(prs, old: int, new: int) -> None:
    ids = prs.slides._sldIdLst
    el = list(ids)[old]
    ids.remove(el)
    ids.insert(new, el)


@tool("pptx_add_slide", "Thêm một slide (layout, tiêu đề, gạch đầu dòng, ghi chú) vào bài có sẵn.", AddSlideArgs,
      kind="pptx", writes=True)
def pptx_add_slide(args: AddSlideArgs, ctx: ToolCtx) -> dict:
    prs = Presentation(ctx.path)
    if not -1 <= args.after < len(prs.slides):
        raise ToolError(f"Vị trí {args.after} không hợp lệ (có {len(prs.slides)} slide)")
    layouts = prs.slide_layouts
    s = prs.slides.add_slide(layouts[min(_LAYOUTS[args.slide.layout], len(layouts) - 1)])
    if s.shapes.title is not None and args.slide.title:
        s.shapes.title.text = args.slide.title
    body = next((ph for ph in s.placeholders if ph.placeholder_format.idx == 1), None)
    if args.slide.bullets and body is not None:
        body.text_frame.text = args.slide.bullets[0]
        for b in args.slide.bullets[1:]:
            body.text_frame.add_paragraph().text = b
    if args.slide.notes:
        s.notes_slide.notes_text_frame.text = args.slide.notes
    _move_slide(prs, len(prs.slides) - 1, args.after + 1)
    prs.save(ctx.path)
    return {"inserted_at": args.after + 1}


class DeleteSlideArgs(BaseModel):
    file: str = FILE
    slide: int = Field(description="Chỉ số slide cần xoá (từ 0)")


@tool("pptx_delete_slide", "Xoá một slide. Thao tác phá huỷ — người dùng sẽ được hỏi xác nhận.", DeleteSlideArgs,
      kind="pptx", writes=True, destructive=True)
def pptx_delete_slide(args: DeleteSlideArgs, ctx: ToolCtx) -> dict:
    _check_selection(ctx, args.slide)
    prs = Presentation(ctx.path)
    _slide(prs, args.slide)
    if len(prs.slides) == 1:
        raise ToolError("Không thể xoá slide duy nhất")
    ids = prs.slides._sldIdLst
    el = list(ids)[args.slide]
    prs.part.drop_rel(el.rId)
    ids.remove(el)
    prs.save(ctx.path)
    return {"deleted": args.slide}


class MoveSlideArgs(BaseModel):
    file: str = FILE
    slide: int = Field(description="Slide cần di chuyển (từ 0)")
    to: int = Field(description="Vị trí mới (từ 0)")


@tool("pptx_move_slide", "Đổi thứ tự slide.", MoveSlideArgs, kind="pptx", writes=True)
def pptx_move_slide(args: MoveSlideArgs, ctx: ToolCtx) -> dict:
    prs = Presentation(ctx.path)
    _slide(prs, args.slide)
    _slide(prs, args.to)
    _move_slide(prs, args.slide, args.to)
    prs.save(ctx.path)
    return {"moved": args.slide, "to": args.to}


class PptTableArgs(BaseModel):
    file: str = FILE
    slide: int
    rows: list[list[str]] = Field(description="Dữ liệu, dòng đầu là tiêu đề. Tối đa ~7 dòng để đọc được")
    left_cm: float = 2
    top_cm: float = 4.5
    width_cm: float = 29.8
    font_pt: int = 14


@tool("pptx_add_table", "Chèn bảng vào slide.", PptTableArgs, kind="pptx", writes=True)
def pptx_add_table(args: PptTableArgs, ctx: ToolCtx) -> dict:
    _check_selection(ctx, args.slide)
    if not args.rows or not args.rows[0]:
        raise ToolError("Bảng cần ít nhất một dòng và một cột")
    prs = Presentation(ctx.path)
    s = _slide(prs, args.slide)
    ncols = max(len(r) for r in args.rows)
    height = Cm(1.0 * len(args.rows))
    table = s.shapes.add_table(len(args.rows), ncols, Cm(args.left_cm), Cm(args.top_cm),
                               Cm(args.width_cm), height).table
    for i, row in enumerate(args.rows):
        for j in range(ncols):
            cell = table.cell(i, j)
            cell.text = str(row[j]) if j < len(row) else ""
            for p in cell.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(args.font_pt)
    prs.save(ctx.path)
    return {"table": f"{len(args.rows)}x{ncols}", "slide": args.slide}


class PptChartArgs(BaseModel):
    file: str = FILE
    slide: int
    chart_type: Literal["column", "bar", "line", "pie"]
    categories: list[str] = Field(description="Nhãn trục X / tên các phần")
    series: dict[str, list[float]] = Field(description="Tên chuỗi → giá trị (cùng độ dài với categories)")
    title: str = ""
    left_cm: float = 2
    top_cm: float = 4
    width_cm: float = 29.8
    height_cm: float = 13


@tool("pptx_add_chart", "Chèn biểu đồ GỐC của PowerPoint (sửa được dữ liệu trong PowerPoint) vào slide.",
      PptChartArgs, kind="pptx", writes=True)
def pptx_add_chart(args: PptChartArgs, ctx: ToolCtx) -> dict:
    _check_selection(ctx, args.slide)
    bad = [k for k, v in args.series.items() if len(v) != len(args.categories)]
    if bad:
        raise ToolError(f"Chuỗi {bad} không cùng số phần tử với categories ({len(args.categories)})")
    prs = Presentation(ctx.path)
    s = _slide(prs, args.slide)
    data = CategoryChartData()
    data.categories = args.categories
    for name, values in args.series.items():
        data.add_series(name, values)
    kind = {"column": XL_CHART_TYPE.COLUMN_CLUSTERED, "bar": XL_CHART_TYPE.BAR_CLUSTERED,
            "line": XL_CHART_TYPE.LINE_MARKERS, "pie": XL_CHART_TYPE.PIE}[args.chart_type]
    chart = s.shapes.add_chart(kind, Cm(args.left_cm), Cm(args.top_cm), Cm(args.width_cm), Cm(args.height_cm),
                               data).chart
    chart.has_legend = len(args.series) > 1 or args.chart_type == "pie"
    if chart.has_legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
    if args.title:
        chart.has_title = True
        chart.chart_title.text_frame.text = args.title
    palette = ["0072B2", "E69F00", "009E73", "D55E00", "CC79A7", "56B4E9"]
    if args.chart_type != "pie":
        for i, ser in enumerate(chart.series):
            ser.format.fill.solid()
            ser.format.fill.fore_color.rgb = RGBColor.from_string(palette[i % len(palette)])
    prs.save(ctx.path)
    return {"chart": args.chart_type, "slide": args.slide}

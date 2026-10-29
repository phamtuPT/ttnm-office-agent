"""Tool PowerPoint (python-pptx): tạo từ mẫu thiết kế, sửa chữ/công thức, slide, bảng, biểu đồ, hình khối."""
from typing import Literal

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.util import Cm, Pt
from pydantic import BaseModel, Field

from .assets import asset_path
from .pptx_design import BUILT_IN, find_layout, new_presentation
from .pptx_math import all_shapes, finalize, shape_markup, write_text
from .registry import ToolCtx, ToolError, tool

FILE = Field(description="Tên tệp .pptx trong phiên")


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
      "ghi chú thuyết trình; công thức toán hiện dạng LaTeX $...$. Luôn gọi trước khi sửa.", InspectArgs, kind="pptx")
def pptx_inspect(args: InspectArgs, ctx: ToolCtx) -> dict:
    prs = Presentation(ctx.path)
    slides = []
    for i, s in enumerate(prs.slides):
        shapes = [{"index": j, "name": sh.name, "text": shape_markup(sh)[:300]}
                  for j, sh in enumerate(all_shapes(s)) if sh.has_text_frame]
        notes = s.notes_slide.notes_text_frame.text[:300] if s.has_notes_slide else ""
        slides.append({"index": i, "layout": s.slide_layout.name, "shapes": shapes, "notes": notes})
    return {"slide_size_cm": [round(prs.slide_width / 360000, 1), round(prs.slide_height / 360000, 1)],
            "slides": slides}


class SlideSpec(BaseModel):
    layout: Literal["title", "title_content", "section", "title_only", "blank"] = "title_content"
    title: str = ""
    bullets: list[str] = Field(default_factory=list, description="Các ý, mỗi ý ngắn gọn (≤ 12 từ). Công thức toán "
                                                                 "viết LaTeX $...$; cả ý là $$...$$ → căn giữa")
    notes: str = Field("", description="Ghi chú thuyết trình")


class CreateArgs(BaseModel):
    file: str = Field(description="Tên tệp mới, đuôi .pptx")
    slides: list[SlideSpec]
    theme: Literal["clean", "midnight", "warm"] = Field(
        "clean", description="Bảng màu: clean = nền trắng chữ xanh đậm; midnight = nền xanh đêm chữ sáng; "
                             "warm = nền kem, tiêu đề cam đất")
    template: str = Field(
        "default_theme", description="Mẫu thiết kế: 'default_theme' (có dải màu nhấn), 'default_plain' (trơn), hoặc "
                                     "tên một tệp .pptx trong phiên để dùng thiết kế của tệp đó (mẫu công ty)")


def _fill_slide(s, spec: "SlideSpec") -> None:
    """Tiêu đề, gạch đầu dòng, ghi chú cho slide mới (chữ có $...$ thành công thức)."""
    if s.shapes.title is not None and spec.title:
        write_text(s.shapes.title, spec.title)
    if spec.bullets:
        body = next((ph for ph in s.placeholders if ph.placeholder_format.idx == 1), None)
        if body is None:
            raise ToolError(f"Layout '{spec.layout}' không có ô nội dung, dùng 'title_content'")
        write_text(body, "\n".join(spec.bullets))
    if spec.notes:
        s.notes_slide.notes_text_frame.text = spec.notes


@tool("pptx_create_presentation", "Tạo bài trình chiếu 16:9 mới từ mẫu thiết kế (hoặc theo thiết kế của một tệp "
      ".pptx có sẵn). Sau khi tạo nên gọi pptx_check_layout / render_pages để tự kiểm tra chữ tràn, chồng lấn.",
      CreateArgs, kind="pptx", creates=True)
def pptx_create_presentation(args: CreateArgs, ctx: ToolCtx) -> dict:
    if args.template in BUILT_IN:
        template, palette = BUILT_IN[args.template], args.theme
    else:  # mẫu của người dùng: giữ nguyên màu của họ
        template, palette = _session_pptx(ctx, args.template), None
    prs = new_presentation(template, palette)
    for spec in args.slides:
        s = prs.slides.add_slide(find_layout(prs, spec.layout))
        _fill_slide(s, spec)
        finalize(s)
    prs.save(ctx.path)
    return {"created": args.file, "slides": len(args.slides), "template": args.template,
            "theme": palette or "theo mẫu"}


def _session_pptx(ctx: ToolCtx, name: str):
    from ..versioning import store  # import muộn: versioning dùng tools
    match = next((f for f in ctx.files if f["name"] == name and f["kind"] == "pptx"), None)
    if match is None:
        pptx_files = [f["name"] for f in ctx.files if f["kind"] == "pptx"]
        raise ToolError(f"Không có mẫu '{name}'. Dùng 'default_theme', 'default_plain' hoặc một tệp: {pptx_files}")
    from ..db import File, SessionLocal
    with SessionLocal() as db:
        return store.working_path(db.get(File, match["id"]))


class TextItem(BaseModel):
    slide: int = Field(description="Chỉ số slide (từ 0)")
    shape: int = Field(description="Chỉ số shape trong slide, lấy từ pptx_inspect")
    text: str = Field(description="Nội dung mới; xuống dòng bằng \\n để tạo nhiều đoạn. Công thức toán viết LaTeX "
                                  "$...$; cả dòng là $$...$$ → công thức căn giữa")


class SetTextArgs(BaseModel):
    file: str = FILE
    items: list[TextItem] = Field(description="Các shape cần sửa — gộp TẤT CẢ thay đổi chữ vào một lần gọi")


@tool("pptx_set_text", "Thay nội dung chữ của các shape (có thể trên nhiều slide), giữ định dạng của đoạn đầu; "
      "$...$ thành công thức toán PowerPoint thật.",
      SetTextArgs, kind="pptx", writes=True)
def pptx_set_text(args: SetTextArgs, ctx: ToolCtx) -> dict:
    if not args.items:
        raise ToolError("Cần ít nhất một mục cần sửa")
    for it in args.items:
        _check_selection(ctx, it.slide)
    prs = Presentation(ctx.path)
    for it in args.items:
        _set_text(prs, it)
    for i in {it.slide for it in args.items}:
        finalize(prs.slides[i])
    prs.save(ctx.path)
    return {"updated": [[it.slide, it.shape] for it in args.items]}


def _set_text(prs, it: TextItem) -> None:
    shapes = all_shapes(_slide(prs, it.slide))
    if not 0 <= it.shape < len(shapes) or not shapes[it.shape].has_text_frame:
        raise ToolError(f"Slide {it.slide}: shape {it.shape} không tồn tại hoặc không chứa chữ")
    write_text(shapes[it.shape], it.text)


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
    slides: list[SlideSpec] = Field(description="Các slide thêm liên tiếp — gộp TẤT CẢ slide cần thêm vào MỘT lần gọi")


def _move_slide(prs, old: int, new: int) -> None:
    ids = prs.slides._sldIdLst
    el = list(ids)[old]
    ids.remove(el)
    ids.insert(new, el)


@tool("pptx_add_slide", "Thêm một hoặc nhiều slide liên tiếp (layout, tiêu đề, gạch đầu dòng, công thức, ghi chú) "
      "vào bài có sẵn, theo mẫu thiết kế của bài.", AddSlideArgs, kind="pptx", writes=True)
def pptx_add_slide(args: AddSlideArgs, ctx: ToolCtx) -> dict:
    if not args.slides:
        raise ToolError("Cần ít nhất một slide")
    prs = Presentation(ctx.path)
    if not -1 <= args.after < len(prs.slides):
        raise ToolError(f"Vị trí {args.after} không hợp lệ (có {len(prs.slides)} slide)")
    for k, spec in enumerate(args.slides):
        s = prs.slides.add_slide(find_layout(prs, spec.layout))
        _fill_slide(s, spec)
        finalize(s)
        _move_slide(prs, len(prs.slides) - 1, args.after + 1 + k)
    prs.save(ctx.path)
    return {"inserted_at": list(range(args.after + 1, args.after + 1 + len(args.slides)))}


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
    if args.chart_type != "pie":
        from pptx.enum.dml import MSO_THEME_COLOR
        for i, ser in enumerate(chart.series):  # màu nhấn của chủ đề (Okabe–Ito) → đổi bảng màu thì đổi theo
            ser.format.fill.solid()
            ser.format.fill.fore_color.theme_color = getattr(MSO_THEME_COLOR, f"ACCENT_{i % 6 + 1}")
    prs.save(ctx.path)
    return {"chart": args.chart_type, "slide": args.slide}


SHAPES = {
    "rectangle": "RECTANGLE", "rounded_rectangle": "ROUNDED_RECTANGLE", "oval": "OVAL", "triangle": "ISOSCELES_TRIANGLE",
    "right_arrow": "RIGHT_ARROW", "left_right_arrow": "LEFT_RIGHT_ARROW", "chevron": "CHEVRON", "pentagon": "PENTAGON",
    "diamond": "DIAMOND", "star": "STAR_5_POINT", "callout": "ROUNDED_RECTANGULAR_CALLOUT", "cloud": "CLOUD",
}
THEME_FILLS = {f"accent{i}": f"ACCENT_{i}" for i in range(1, 7)} | {"dark": "TEXT_2", "light": "BACKGROUND_2"}


class ShapeItem(BaseModel):
    kind: Literal["rectangle", "rounded_rectangle", "oval", "triangle", "right_arrow", "left_right_arrow", "chevron",
                  "pentagon", "diamond", "star", "callout", "cloud", "text_box"] = "rounded_rectangle"
    left_cm: float = Field(description="Slide 16:9 rộng 33,9 cm, cao 19,05 cm; chừa lề ≥ 1,9 cm")
    top_cm: float
    width_cm: float
    height_cm: float
    text: str = Field("", description="Chữ trong hình; \n xuống dòng; công thức toán viết LaTeX $...$")
    fill: str = Field("accent1", description="'accent1'..'accent6', 'dark', 'light' (màu theo bảng màu của bài, đổi "
                                             "chủ đề vẫn hợp), 'none' hoặc mã '#RRGGBB'")
    font_pt: int = Field(18, ge=8, le=60)
    bold: bool = False


class AddShapeArgs(BaseModel):
    file: str = FILE
    slide: int = Field(description="Chỉ số slide (từ 0)")
    shapes: list[ShapeItem] = Field(description="Các hình — vẽ cả sơ đồ (quy trình, so sánh, chu trình) trong MỘT lần gọi")


@tool("pptx_add_shape", "Vẽ hình khối/hộp chữ lên slide: sơ đồ quy trình (chevron, mũi tên), khối so sánh, chú thích, "
      "nhãn; có thể chứa chữ và công thức toán.", AddShapeArgs, kind="pptx", writes=True)
def pptx_add_shape(args: AddShapeArgs, ctx: ToolCtx) -> dict:
    from pptx.enum.dml import MSO_THEME_COLOR
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

    if not args.shapes:
        raise ToolError("Cần ít nhất một hình")
    _check_selection(ctx, args.slide)
    prs = Presentation(ctx.path)
    s = _slide(prs, args.slide)
    w, h = prs.slide_width / 360000, prs.slide_height / 360000
    added = []
    for it in args.shapes:
        if it.left_cm < 0 or it.top_cm < 0 or it.left_cm + it.width_cm > w + 0.01 or it.top_cm + it.height_cm > h + 0.01:
            raise ToolError(f"Hình '{it.text[:20] or it.kind}' nằm ngoài slide ({w:.1f} × {h:.1f} cm)")
        box = (Cm(it.left_cm), Cm(it.top_cm), Cm(it.width_cm), Cm(it.height_cm))
        sh = s.shapes.add_textbox(*box) if it.kind == "text_box" else \
            s.shapes.add_shape(getattr(MSO_SHAPE, SHAPES[it.kind]), *box)
        filled = it.kind != "text_box" and it.fill != "none"
        if it.kind != "text_box":
            if not filled:
                sh.fill.background()
            elif it.fill in THEME_FILLS:
                sh.fill.solid()
                sh.fill.fore_color.theme_color = getattr(MSO_THEME_COLOR, THEME_FILLS[it.fill])
            else:
                try:
                    sh.fill.solid()
                    sh.fill.fore_color.rgb = RGBColor.from_string(it.fill.lstrip("#").upper())
                except ValueError:
                    raise ToolError(f"Màu '{it.fill}' không hợp lệ: dùng accent1..accent6, dark, light, none, #RRGGBB")
            sh.line.fill.background()
        if it.text:
            write_text(sh, it.text)
            tf = sh.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            for p in tf.paragraphs:
                if it.kind != "text_box":
                    p.alignment = PP_ALIGN.CENTER
                for r in p.runs:
                    r.font.size = Pt(it.font_pt)
                    r.font.bold = it.bold
                    # Chữ trên nền màu nhấn/đậm: màu nền slide (lt1) cho đủ tương phản; hình trống: màu chữ thường
                    r.font.color.theme_color = MSO_THEME_COLOR.BACKGROUND_1 if filled and it.fill != "light" \
                        else MSO_THEME_COLOR.TEXT_1
        added.append(sh.shape_id)
    finalize(s)
    ids = [x.shape_id for x in all_shapes(s)]
    prs.save(ctx.path)
    return {"slide": args.slide, "shapes": [ids.index(i) for i in added]}


class ThemeArgs(BaseModel):
    file: str = FILE
    theme: Literal["clean", "midnight", "warm"] = Field(description="Bảng màu mới cho cả bài")


@tool("pptx_set_theme", "Đổi bảng màu của cả bài trình chiếu (nền, tiêu đề, chữ, màu nhấn, biểu đồ) — áp dụng cho "
      "mọi slide dùng màu chủ đề.", ThemeArgs, kind="pptx", writes=True)
def pptx_set_theme(args: ThemeArgs, ctx: ToolCtx) -> dict:
    from .pptx_design import apply_palette
    prs = Presentation(ctx.path)
    apply_palette(prs, args.theme)
    prs.save(ctx.path)
    return {"theme": args.theme}


class CheckArgs(BaseModel):
    file: str = FILE
    slides: list[int] | None = Field(None, description="Chỉ kiểm tra các slide này (từ 0); bỏ trống = cả bài")


@tool("pptx_check_layout", "Tự kiểm tra bố cục slide (không cần ảnh): chữ tràn khung, hình chồng lấn, hình ra ngoài "
      "slide. Gọi sau khi tạo/sửa slide; có lỗi thì sửa rồi kiểm tra lại.", CheckArgs, kind="pptx")
def pptx_check_layout(args: CheckArgs, ctx: ToolCtx) -> dict:
    from .layout_check import check_presentation
    prs = Presentation(ctx.path)
    issues = check_presentation(prs, args.slides)
    return {"issues": issues[:30], "issue_count": len(issues),
            "checked_slides": len(args.slides) if args.slides is not None else len(prs.slides)}

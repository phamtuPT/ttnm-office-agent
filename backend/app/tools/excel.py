"""Tool Excel (openpyxl). TV2 mở rộng: sắp xếp, lọc, thanh sai số, định dạng từ khoá, ...

openpyxl không tính công thức; giá trị công thức chỉ có sau khi mở bằng Excel/LibreOffice.
TODO(TV1/TV2): tính lại bằng LibreOffice headless và trả lỗi #REF!/#NAME? cho LLM.
"""
from copy import copy

import openpyxl
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.chart.data_source import NumDataSource, NumRef
from openpyxl.chart.error_bar import ErrorBars
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries
from pydantic import BaseModel, Field
from typing import Literal

from .registry import ToolCtx, ToolError, tool
from .xlsx_util import chart_info, check_formula

MAX_READ_CELLS = 500
MAX_WRITE_CELLS = 500
# Bảng màu Okabe–Ito: phân biệt được với người mù màu
CHART_COLORS = ["0072B2", "E69F00", "009E73", "D55E00", "CC79A7", "56B4E9", "F0E442", "000000"]

FILE = Field(description="Tên tệp .xlsx trong phiên")
SHEET = Field(description="Tên sheet")
Value = str | float | bool | None


def _load(ctx: ToolCtx):
    return openpyxl.load_workbook(ctx.path, rich_text=True)


def _sheet(wb, name: str):
    if name not in wb.sheetnames:
        raise ToolError(f"Không có sheet '{name}'. Các sheet hiện có: {wb.sheetnames}")
    return wb[name]


def _bounds(rng: str) -> tuple[int, int, int, int]:
    try:
        return range_boundaries(rng)
    except (ValueError, TypeError):
        raise ToolError(f"Vùng ô không hợp lệ: {rng}")


def _val(v):
    return v if v is None or isinstance(v, (int, float, str, bool)) else str(v)


def _check_selection(ctx: ToolCtx, sheet: str, refs: list[str]) -> None:
    sel = ctx.selection
    if not sel or not sel.range:
        return
    if sel.sheet and sel.sheet != sheet:
        raise ToolError(f"Người dùng chỉ cho phép sửa sheet '{sel.sheet}', vùng {sel.range}")
    min_c, min_r, max_c, max_r = range_boundaries(sel.range)
    outside = [r for r in refs
               if not (min_r <= coordinate_to_tuple(r)[0] <= max_r and min_c <= coordinate_to_tuple(r)[1] <= max_c)]
    if outside:
        raise ToolError(f"Các ô {outside[:10]} nằm ngoài vùng người dùng chọn ({sel.range})")


def _range_refs(rng: str) -> list[str]:
    min_c, min_r, max_c, max_r = _bounds(rng)
    return [openpyxl.utils.get_column_letter(c) + str(r)
            for r in range(min_r, max_r + 1) for c in range(min_c, max_c + 1)]


# ---------- Đọc ----------

class InspectArgs(BaseModel):
    file: str = FILE


@tool("excel_inspect", "Xem cấu trúc workbook: danh sách sheet, kích thước dữ liệu, số biểu đồ và 6 dòng đầu "
      "(công thức hiển thị dạng '=...'). Luôn gọi trước khi đọc chi tiết hoặc sửa.", InspectArgs, kind="xlsx")
def excel_inspect(args: InspectArgs, ctx: ToolCtx) -> dict:
    wb = _load(ctx)
    sheets = []
    for ws in wb.worksheets:
        rows = [[_val(v) for v in row]
                for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 6), values_only=True)]
        sheets.append({"name": ws.title, "dimensions": ws.dimensions, "max_row": ws.max_row,
                       "max_column": ws.max_column, "charts": chart_info(ws),
                       "filter": ws.auto_filter.ref, "first_rows": rows})
    return {"sheets": sheets}


class ReadRangeArgs(BaseModel):
    file: str = FILE
    sheet: str = SHEET
    range: str = Field(description=f"Vùng ô dạng A1:D20, tối đa {MAX_READ_CELLS} ô")


@tool("excel_read_range", "Đọc giá trị/công thức của một vùng ô.", ReadRangeArgs, kind="xlsx")
def excel_read_range(args: ReadRangeArgs, ctx: ToolCtx) -> dict:
    ws = _sheet(_load(ctx), args.sheet)
    min_c, min_r, max_c, max_r = _bounds(args.range)
    if (max_c - min_c + 1) * (max_r - min_r + 1) > MAX_READ_CELLS:
        raise ToolError(f"Vùng quá lớn, hãy đọc tối đa {MAX_READ_CELLS} ô mỗi lần")
    rows = [[_val(v) for v in row]
            for row in ws.iter_rows(min_row=min_r, max_row=max_r, min_col=min_c, max_col=max_c, values_only=True)]
    return {"sheet": args.sheet, "range": args.range, "rows": rows}


# ---------- Tạo ----------

class SheetSpec(BaseModel):
    name: str = Field(description="Tên sheet")
    rows: list[list[Value]] = Field(default_factory=list,
                                    description="Dữ liệu từ ô A1, mỗi phần tử là một dòng. Chuỗi bắt đầu '=' là công thức")
    bold_header: bool = Field(True, description="In đậm dòng đầu")


class CreateArgs(BaseModel):
    file: str = Field(description="Tên tệp mới, đuôi .xlsx, ví dụ doanh-thu-2026.xlsx")
    sheets: list[SheetSpec] = Field(description="Các sheet cần tạo, ít nhất một")


@tool("excel_create_workbook", "Tạo tệp Excel mới với các sheet và dữ liệu ban đầu.", CreateArgs,
      kind="xlsx", creates=True)
def excel_create_workbook(args: CreateArgs, ctx: ToolCtx) -> dict:
    if not args.sheets:
        raise ToolError("Cần ít nhất một sheet")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for spec in args.sheets:
        ws = wb.create_sheet(spec.name[:31])
        for row in spec.rows:
            ws.append(row)
        if spec.bold_header and spec.rows:
            for c in ws[1]:
                c.font = Font(bold=True)
        for col in ws.columns:  # độ rộng cột vừa nội dung
            width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
            ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 8), 50)
    wb.save(ctx.path)
    return {"created": args.file, "sheets": [s.name for s in args.sheets]}


class AddSheetArgs(BaseModel):
    file: str = FILE
    sheets: list[SheetSpec] = Field(description="Các sheet mới (tên chưa có trong tệp) kèm dữ liệu từ ô A1; công thức "
                                                "được tham chiếu sang sheet khác, ví dụ =COUNTIF('Nhân sự'!C:C,A2)")


@tool("excel_add_sheet", "Thêm sheet mới vào tệp Excel có sẵn (bảng thống kê, tổng hợp, dự báo...) kèm dữ liệu và "
      "công thức.", AddSheetArgs, kind="xlsx", writes=True)
def excel_add_sheet(args: AddSheetArgs, ctx: ToolCtx) -> dict:
    if not args.sheets:
        raise ToolError("Cần ít nhất một sheet")
    wb = openpyxl.load_workbook(ctx.path)
    taken = [n.lower() for n in wb.sheetnames]
    clash = [s.name for s in args.sheets if s.name[:31].lower() in taken]
    if clash:
        raise ToolError(f"Đã có sheet {clash}; dùng excel_write_cells để ghi vào sheet đó hoặc chọn tên khác")
    names = wb.sheetnames + [s.name[:31] for s in args.sheets]
    issues = []
    for spec in args.sheets:
        ws = wb.create_sheet(spec.name[:31])
        for r, row in enumerate(spec.rows, start=1):
            for c, value in enumerate(row, start=1):
                if isinstance(value, str) and value.startswith("="):
                    value, problems = check_formula(value, names)
                    if problems:
                        issues.append({"sheet": spec.name, "cell": ws.cell(r, c).coordinate, "problems": problems})
                ws.cell(r, c, value)
        if spec.bold_header and spec.rows:
            for c in ws[1]:
                c.font = Font(bold=True)
    if issues:
        raise ToolError(f"Công thức có lỗi, chưa thêm sheet nào: {issues[:10]}")
    wb.save(ctx.path)
    return {"added": [s.name for s in args.sheets]}


# ---------- Ghi ----------

class CellWrite(BaseModel):
    ref: str = Field(description="Địa chỉ ô, ví dụ B2")
    value: Value = Field(
        description="Giá trị mới. Chuỗi bắt đầu bằng '=' là công thức (cú pháp Excel tiếng Anh, ví dụ =SUM(B2:B10)). "
                    "null để xoá ô.")


class WriteCellsArgs(BaseModel):
    file: str = FILE
    sheet: str = SHEET
    cells: list[CellWrite] = Field(description=f"Danh sách ô cần ghi, tối đa {MAX_WRITE_CELLS}")


@tool("excel_write_cells", "Ghi giá trị hoặc công thức vào các ô. Kết quả liệt kê các ô có dữ liệu cũ đã bị ghi đè.",
      WriteCellsArgs, kind="xlsx", writes=True)
def excel_write_cells(args: WriteCellsArgs, ctx: ToolCtx) -> dict:
    if len(args.cells) > MAX_WRITE_CELLS:
        raise ToolError(f"Tối đa {MAX_WRITE_CELLS} ô mỗi lần ghi")
    for c in args.cells:
        try:
            coordinate_to_tuple(c.ref)
        except ValueError:
            raise ToolError(f"Địa chỉ ô không hợp lệ: {c.ref}")
    _check_selection(ctx, args.sheet, [c.ref for c in args.cells])
    wb = _load(ctx)
    ws = _sheet(wb, args.sheet)
    overwritten, formula_issues = [], []
    for c in args.cells:
        value = c.value
        if isinstance(value, str) and value.startswith("="):
            value, problems = check_formula(value, wb.sheetnames)
            if problems:
                formula_issues.append({"ref": c.ref, "problems": problems})
        old = ws[c.ref].value
        if old not in (None, "") and old != value:
            overwritten.append({"ref": c.ref, "old": _val(old)})
        ws[c.ref] = value
    if formula_issues:
        # Không ghi gì cả: công thức lỗi sẽ hiện #NAME?/#REF! trong Excel
        raise ToolError(f"Công thức có lỗi, chưa ghi ô nào: {formula_issues[:10]}")
    wb.save(ctx.path)
    out = {"written": len(args.cells)}
    if overwritten:
        out["overwritten"] = overwritten[:20]
        out["note"] = f"Đã ghi đè {len(overwritten)} ô có dữ liệu — nhắc người dùng nếu họ không yêu cầu điều này"
    return out


class FormatArgs(BaseModel):
    file: str = FILE
    sheet: str = SHEET
    range: str = Field(description="Vùng ô dạng A1:D20")
    number_format: str | None = Field(None, description="Định dạng số Excel, ví dụ '#,##0' hoặc '0.00%'")
    bold: bool | None = None
    italic: bool | None = None
    font_color: str | None = Field(None, description="Màu chữ hex RRGGBB, ví dụ FF0000")
    fill_color: str | None = Field(None, description="Màu nền hex RRGGBB, ví dụ FFFF00")


@tool("excel_format_range", "Định dạng một vùng ô: định dạng số, in đậm/nghiêng, màu chữ, màu nền.", FormatArgs,
      kind="xlsx", writes=True)
def excel_format_range(args: FormatArgs, ctx: ToolCtx) -> dict:
    _check_selection(ctx, args.sheet, _range_refs(args.range))
    wb = _load(ctx)
    ws = _sheet(wb, args.sheet)
    min_c, min_r, max_c, max_r = _bounds(args.range)
    cells = [c for row in ws.iter_rows(min_row=min_r, max_row=max_r, min_col=min_c, max_col=max_c) for c in row]
    for c in cells:
        if args.number_format is not None:
            c.number_format = args.number_format
        if args.bold is not None or args.italic is not None or args.font_color:
            font = copy(c.font)
            if args.bold is not None:
                font.bold = args.bold
            if args.italic is not None:
                font.italic = args.italic
            if args.font_color:
                font.color = args.font_color.lstrip("#")
            c.font = font
        if args.fill_color:
            c.fill = PatternFill("solid", fgColor=args.fill_color.lstrip("#"))
    wb.save(ctx.path)
    return {"formatted": len(cells)}


class ConditionalArgs(BaseModel):
    file: str = FILE
    sheet: str = SHEET
    range: str = Field(description="Vùng áp dụng, ví dụ B2:D10")
    operator: Literal["lessThan", "lessThanOrEqual", "greaterThan", "greaterThanOrEqual", "equal", "notEqual",
                      "between"] = Field(description="Phép so sánh")
    value: float | str = Field(description="Ngưỡng so sánh (giá trị dưới với 'between')")
    value2: float | str | None = Field(None, description="Giá trị trên, chỉ dùng với 'between'")
    font_color: str | None = Field(None, description="Màu chữ hex, ví dụ C00000")
    fill_color: str | None = Field(None, description="Màu nền hex, ví dụ FFC7CE")


@tool("excel_conditional_format", "Tô màu có điều kiện (ví dụ tô đỏ giá trị âm: operator=lessThan, value=0). "
      "Tự cập nhật khi dữ liệu đổi.", ConditionalArgs, kind="xlsx", writes=True)
def excel_conditional_format(args: ConditionalArgs, ctx: ToolCtx) -> dict:
    _check_selection(ctx, args.sheet, _range_refs(args.range))
    if not args.font_color and not args.fill_color:
        raise ToolError("Cần ít nhất font_color hoặc fill_color")
    formula = [str(args.value)] + ([str(args.value2)] if args.operator == "between" and args.value2 is not None else [])
    if args.operator == "between" and len(formula) < 2:
        raise ToolError("'between' cần value2")
    wb = _load(ctx)
    ws = _sheet(wb, args.sheet)
    rule = CellIsRule(operator=args.operator, formula=formula,
                      font=Font(color=args.font_color.lstrip("#")) if args.font_color else None,
                      fill=PatternFill("solid", bgColor=args.fill_color.lstrip("#")) if args.fill_color else None)
    ws.conditional_formatting.add(args.range, rule)
    wb.save(ctx.path)
    return {"applied": args.range}


class ChartArgs(BaseModel):
    file: str = FILE
    sheet: str = SHEET
    chart_type: Literal["column", "bar", "line", "pie"] = Field(description="column=cột đứng, bar=thanh ngang")
    data_range: str = Field(description="Vùng dữ liệu GỒM dòng tiêu đề, có thể nhiều cột (mỗi cột một chuỗi), ví dụ B1:C13")
    categories_range: str | None = Field(None, description="Vùng nhãn trục X KHÔNG gồm tiêu đề, ví dụ A2:A13")
    title: str = ""
    anchor: str = Field("H2", description="Ô đặt góc trên trái biểu đồ")
    x_title: str | None = None
    y_title: str | None = None
    error_range: str | None = Field(None, description="Vùng chứa độ lớn thanh sai số (±) cho chuỗi đầu tiên, "
                                                       "cùng số ô với dữ liệu, KHÔNG gồm tiêu đề, ví dụ C2:C13")


@tool("excel_add_chart", "Thêm biểu đồ Excel GỐC gắn với vùng ô (sửa số liệu thì biểu đồ tự cập nhật), "
      "dùng bảng màu thân thiện với người mù màu.", ChartArgs, kind="xlsx", writes=True)
def excel_add_chart(args: ChartArgs, ctx: ToolCtx) -> dict:
    wb = _load(ctx)
    ws = _sheet(wb, args.sheet)
    _bounds(args.data_range)
    q = f"'{args.sheet}'!"
    chart = {"column": BarChart, "bar": BarChart, "line": LineChart, "pie": PieChart}[args.chart_type]()
    if args.chart_type in ("column", "bar"):
        chart.type = "col" if args.chart_type == "column" else "bar"
    chart.add_data(Reference(ws, range_string=q + args.data_range), titles_from_data=True)
    if args.categories_range:
        _bounds(args.categories_range)
        chart.set_categories(Reference(ws, range_string=q + args.categories_range))
    if args.title:
        chart.title = args.title
    if args.chart_type != "pie":
        if args.x_title:
            chart.x_axis.title = args.x_title
        if args.y_title:
            chart.y_axis.title = args.y_title
        for i, s in enumerate(chart.series):
            color = CHART_COLORS[i % len(CHART_COLORS)]
            s.graphicalProperties.solidFill = color
            s.graphicalProperties.line.solidFill = color
        if args.error_range:
            _bounds(args.error_range)
            chart.series[0].errBars = ErrorBars(
                errDir="y", errBarType="both", errValType="cust",
                plus=NumDataSource(numRef=NumRef(f=q + args.error_range)),
                minus=NumDataSource(numRef=NumRef(f=q + args.error_range)))
    chart.width, chart.height = 16, 8
    ws.add_chart(chart, args.anchor)
    wb.save(ctx.path)
    return {"chart": args.chart_type, "series": len(chart.series), "anchor": args.anchor}


class DeleteSheetArgs(BaseModel):
    file: str = FILE
    sheet: str = SHEET


@tool("excel_delete_sheet", "Xoá một sheet. Thao tác phá huỷ — người dùng sẽ được hỏi xác nhận.",
      DeleteSheetArgs, kind="xlsx", writes=True, destructive=True)
def excel_delete_sheet(args: DeleteSheetArgs, ctx: ToolCtx) -> dict:
    wb = _load(ctx)
    ws = _sheet(wb, args.sheet)
    if len(wb.sheetnames) == 1:
        raise ToolError("Không thể xoá sheet duy nhất của workbook")
    wb.remove(ws)
    wb.save(ctx.path)
    return {"deleted": args.sheet}


class SortArgs(BaseModel):
    file: str = FILE
    sheet: str = SHEET
    range: str = Field(description="Vùng dữ liệu cần sắp xếp KHÔNG gồm dòng tiêu đề, ví dụ A2:D50")
    by_column: str = Field(description="Cột làm khoá sắp xếp, ví dụ C")
    descending: bool = False


@tool("excel_sort_range", "Sắp xếp các dòng trong một vùng theo một cột (giữ định dạng từng ô). "
      "Vùng có công thức sẽ bị từ chối vì sắp xếp làm sai tham chiếu.", SortArgs, kind="xlsx", writes=True)
def excel_sort_range(args: SortArgs, ctx: ToolCtx) -> dict:
    _check_selection(ctx, args.sheet, _range_refs(args.range))
    min_c, min_r, max_c, max_r = _bounds(args.range)
    try:
        key = openpyxl.utils.column_index_from_string(args.by_column.upper())
    except ValueError:
        raise ToolError(f"Cột không hợp lệ: {args.by_column}")
    if not min_c <= key <= max_c:
        raise ToolError(f"Cột {args.by_column} nằm ngoài vùng {args.range}")
    wb = _load(ctx)
    ws = _sheet(wb, args.sheet)
    rows = [[(c.value, copy(c._style)) for c in row]
            for row in ws.iter_rows(min_row=min_r, max_row=max_r, min_col=min_c, max_col=max_c)]
    if any(isinstance(v, str) and v.startswith("=") for row in rows for v, _ in row):
        raise ToolError("Vùng có công thức — sắp xếp sẽ làm sai tham chiếu. Hãy sắp xếp vùng chỉ chứa giá trị")
    filled = [r for r in rows if r[key - min_c][0] is not None]
    empty = [r for r in rows if r[key - min_c][0] is None]  # ô trống luôn nằm cuối
    filled.sort(key=lambda r: (isinstance(r[key - min_c][0], str), r[key - min_c][0]), reverse=args.descending)
    for r_off, row in enumerate(filled + empty):
        for c_off, (v, style) in enumerate(row):
            cell = ws.cell(min_r + r_off, min_c + c_off)
            cell.value, cell._style = v, style
    wb.save(ctx.path)
    return {"sorted_rows": len(rows), "by": args.by_column, "descending": args.descending}


class FilterArgs(BaseModel):
    file: str = FILE
    sheet: str = SHEET
    range: str | None = Field(description="Vùng bảng GỒM dòng tiêu đề, ví dụ A1:D50; null để bỏ bộ lọc")


@tool("excel_set_filter", "Bật/tắt bộ lọc (AutoFilter) cho bảng để người dùng lọc trong Excel.", FilterArgs,
      kind="xlsx", writes=True)
def excel_set_filter(args: FilterArgs, ctx: ToolCtx) -> dict:
    if args.range:
        _bounds(args.range)
    wb = _load(ctx)
    ws = _sheet(wb, args.sheet)
    ws.auto_filter.ref = args.range
    wb.save(ctx.path)
    return {"filter": args.range}

"""Tool Excel (openpyxl). TV2 mở rộng: sắp xếp, lọc, biểu đồ, định dạng có điều kiện, ...

openpyxl không tính công thức; giá trị công thức chỉ có sau khi mở bằng Excel/LibreOffice.
TODO(TV1/TV2, giai đoạn 4): tính lại bằng LibreOffice headless và trả lỗi #REF!/#NAME? cho LLM.
"""
from copy import copy

import openpyxl
from openpyxl.styles import PatternFill
from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries
from pydantic import BaseModel, Field

from .registry import ToolCtx, ToolError, tool

MAX_READ_CELLS = 500
MAX_WRITE_CELLS = 500

FILE = Field(description="Tên tệp .xlsx trong phiên")
SHEET = Field(description="Tên sheet")


def _load(ctx: ToolCtx):
    return openpyxl.load_workbook(ctx.path)


def _sheet(wb, name: str):
    if name not in wb.sheetnames:
        raise ToolError(f"Không có sheet '{name}'. Các sheet hiện có: {wb.sheetnames}")
    return wb[name]


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


class InspectArgs(BaseModel):
    file: str = FILE


@tool("excel_inspect", "Xem cấu trúc workbook: danh sách sheet, kích thước dữ liệu và 6 dòng đầu "
      "(công thức hiển thị dạng '=...'). Luôn gọi trước khi đọc chi tiết hoặc sửa.", InspectArgs, kind="xlsx")
def excel_inspect(args: InspectArgs, ctx: ToolCtx) -> dict:
    wb = _load(ctx)
    sheets = []
    for ws in wb.worksheets:
        rows = [[_val(v) for v in row]
                for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 6), values_only=True)]
        sheets.append({"name": ws.title, "dimensions": ws.dimensions,
                       "max_row": ws.max_row, "max_column": ws.max_column, "first_rows": rows})
    return {"sheets": sheets}


class ReadRangeArgs(BaseModel):
    file: str = FILE
    sheet: str = SHEET
    range: str = Field(description=f"Vùng ô dạng A1:D20, tối đa {MAX_READ_CELLS} ô")


@tool("excel_read_range", "Đọc giá trị/công thức của một vùng ô.", ReadRangeArgs, kind="xlsx")
def excel_read_range(args: ReadRangeArgs, ctx: ToolCtx) -> dict:
    ws = _sheet(_load(ctx), args.sheet)
    try:
        min_c, min_r, max_c, max_r = range_boundaries(args.range)
    except ValueError:
        raise ToolError(f"Vùng ô không hợp lệ: {args.range}")
    if (max_c - min_c + 1) * (max_r - min_r + 1) > MAX_READ_CELLS:
        raise ToolError(f"Vùng quá lớn, hãy đọc tối đa {MAX_READ_CELLS} ô mỗi lần")
    rows = [[_val(v) for v in row]
            for row in ws.iter_rows(min_row=min_r, max_row=max_r, min_col=min_c, max_col=max_c, values_only=True)]
    return {"sheet": args.sheet, "range": args.range, "rows": rows}


class CellWrite(BaseModel):
    ref: str = Field(description="Địa chỉ ô, ví dụ B2")
    value: str | float | bool | None = Field(
        description="Giá trị mới. Chuỗi bắt đầu bằng '=' là công thức (cú pháp Excel tiếng Anh, ví dụ =SUM(B2:B10)). "
                    "null để xoá ô.")


class WriteCellsArgs(BaseModel):
    file: str = FILE
    sheet: str = SHEET
    cells: list[CellWrite] = Field(description=f"Danh sách ô cần ghi, tối đa {MAX_WRITE_CELLS}")


@tool("excel_write_cells", "Ghi giá trị hoặc công thức vào các ô.", WriteCellsArgs, kind="xlsx", writes=True)
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
    for c in args.cells:
        ws[c.ref] = c.value
    wb.save(ctx.path)
    return {"written": len(args.cells)}


class FormatArgs(BaseModel):
    file: str = FILE
    sheet: str = SHEET
    range: str = Field(description="Vùng ô dạng A1:D20")
    number_format: str | None = Field(None, description="Định dạng số Excel, ví dụ '#,##0' hoặc '0.00%'")
    bold: bool | None = None
    fill_color: str | None = Field(None, description="Màu nền dạng hex RRGGBB, ví dụ FFFF00")


@tool("excel_format_range", "Định dạng một vùng ô: định dạng số, in đậm, màu nền.", FormatArgs,
      kind="xlsx", writes=True)
def excel_format_range(args: FormatArgs, ctx: ToolCtx) -> dict:
    try:
        min_c, min_r, max_c, max_r = range_boundaries(args.range)
    except ValueError:
        raise ToolError(f"Vùng ô không hợp lệ: {args.range}")
    wb = _load(ctx)
    ws = _sheet(wb, args.sheet)
    cells = [c for row in ws.iter_rows(min_row=min_r, max_row=max_r, min_col=min_c, max_col=max_c) for c in row]
    _check_selection(ctx, args.sheet, [c.coordinate for c in cells])
    for c in cells:
        if args.number_format is not None:
            c.number_format = args.number_format
        if args.bold is not None:
            font = copy(c.font)
            font.bold = args.bold
            c.font = font
        if args.fill_color:
            c.fill = PatternFill("solid", fgColor=args.fill_color.lstrip("#"))
    wb.save(ctx.path)
    return {"formatted": len(cells)}


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


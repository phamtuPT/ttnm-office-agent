import FormulaParser from "fast-formula-parser";
import * as XLSX from "xlsx";

/**
 * Tính kết quả công thức để hiển thị trong lưới xem trước.
 *
 * Tệp do openpyxl ghi chỉ có công thức, chưa có giá trị đã tính (Excel tự tính khi mở). Ở đây tính lại bằng bộ máy
 * công thức JavaScript (fast-formula-parser, MIT). Hàm bộ máy chưa hỗ trợ (ví dụ XLOOKUP) → `unsupported`, giao diện
 * hiện nguyên công thức thay vì một con số có thể sai.
 */
export interface CellResult {
  value: string | number | boolean | null;
  error?: string; // #DIV/0!, #REF!, #NAME?, #VALUE!...
  unsupported?: boolean;
}

const MAX_CELLS = 200_000; // chặn vùng quá lớn (ví dụ A:Z trên trang tính lớn)

export function createEvaluator(wb: XLSX.WorkBook) {
  const memo = new Map<string, CellResult>();
  const visiting = new Set<string>();

  const bounds = (sheet: string) => XLSX.utils.decode_range(wb.Sheets[sheet]?.["!ref"] ?? "A1");

  const valueAt = (sheet: string, r: number, c: number): unknown => {
    const cell = wb.Sheets[sheet]?.[XLSX.utils.encode_cell({ r, c })] as XLSX.CellObject | undefined;
    if (!cell) return null;
    if (cell.f) {
      const res = evaluate(sheet, r, c, cell.f);
      if (res.error || res.unsupported) throw new Error(res.error ?? "#N/A");
      return res.value;
    }
    return cell.t === "z" || cell.v === undefined ? null : cell.v;
  };

  const parser = new FormulaParser({
    onCell: ({ sheet, row, col }) => valueAt(sheet, row - 1, col - 1),
    onRange: ({ sheet, from, to }) => {
      const b = bounds(sheet);
      const r2 = Math.min(to.row - 1, b.e.r);
      const c2 = Math.min(to.col - 1, b.e.c);
      if ((r2 - from.row + 2) * (c2 - from.col + 2) > MAX_CELLS) throw new Error("#RANGE");
      const rows: unknown[][] = [];
      for (let r = from.row - 1; r <= r2; r++) {
        const row: unknown[] = [];
        for (let c = from.col - 1; c <= c2; c++) row.push(valueAt(sheet, r, c));
        rows.push(row);
      }
      return rows.length ? rows : [[null]];
    },
  });

  function evaluate(sheet: string, r: number, c: number, formula: string): CellResult {
    const key = `${sheet}!${r},${c}`;
    const hit = memo.get(key);
    if (hit) return hit;
    if (visiting.has(key)) return { value: null, error: "#CIRC!" }; // tham chiếu vòng
    visiting.add(key);
    let res: CellResult;
    try {
      const out = parser.parse(formula.replace(/_xlfn\./gi, ""), { sheet, row: r + 1, col: c + 1 });
      const v = Array.isArray(out) ? (Array.isArray(out[0]) ? out[0][0] : out[0]) : out;
      res = v instanceof FormulaParser.FormulaError
        ? { value: null, error: String(v) }
        : { value: (v ?? null) as CellResult["value"] };
    } catch (e) {
      const msg = String((e as Error)?.message ?? e);
      res = /not implemented/i.test(msg) ? { value: null, unsupported: true } : { value: null, error: msg.split(":")[0] || "#ERROR!" };
    }
    visiting.delete(key);
    memo.set(key, res);
    return res;
  }

  return {
    /** Kết quả của ô công thức tại (r, c), chỉ số từ 0. */
    cell: (sheet: string, r: number, c: number, formula: string) => evaluate(sheet, r, c, formula),
  };
}

/** Định dạng giá trị theo định dạng số của ô (z), như Excel hiển thị: 217950000 + "#,##0" → "217,950,000". */
export function formatValue(value: CellResult["value"], numFmt?: string | number): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number" && numFmt !== undefined && numFmt !== "General") {
    try {
      return XLSX.SSF.format(numFmt, value);
    } catch {
      /* định dạng lạ → hiện số thô */
    }
  }
  if (typeof value === "boolean") return value ? "TRUE" : "FALSE";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Math.round(value * 1e10) / 1e10);
  return String(value);
}

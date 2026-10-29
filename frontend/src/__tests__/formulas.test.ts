import * as XLSX from "xlsx";
import { describe, expect, it } from "vitest";
import { createEvaluator, formatValue } from "../formulas";

function book(cells: Record<string, XLSX.CellObject>, ref = "A1:E12") {
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, { ...cells, "!ref": ref } as XLSX.WorkSheet, "S");
  return createEvaluator(wb);
}

describe("createEvaluator", () => {
  it("tính công thức như Excel, kể cả công thức lồng nhau và hàm có tiền tố _xlfn.", () => {
    const ev = book({
      E2: { t: "n", v: 28500000 }, E3: { t: "n", v: 16000000 }, E4: { t: "n", v: 31000000 },
      E5: { t: "z", f: "SUM(E2:E4)" } as XLSX.CellObject,
      E6: { t: "z", f: "E5/3" } as XLSX.CellObject,
      E7: { t: "z", f: "_xlfn.IFS(E5>0,\"dương\",TRUE,\"âm\")" } as XLSX.CellObject,
    });
    expect(ev.cell("S", 4, 4, "SUM(E2:E4)")).toEqual({ value: 75500000 });
    expect(ev.cell("S", 5, 4, "E5/3").value).toBeCloseTo(25166666.67, 1);
    expect(ev.cell("S", 6, 4, "_xlfn.IFS(E5>0,\"dương\",TRUE,\"âm\")").value).toBe("dương");
  });

  it("báo lỗi Excel, hàm chưa hỗ trợ và tham chiếu vòng", () => {
    const ev = book({
      A1: { t: "z", f: "1/0" } as XLSX.CellObject,
      A2: { t: "z", f: "FOOBAR(1)" } as XLSX.CellObject,
      A3: { t: "z", f: "A4+1" } as XLSX.CellObject,
      A4: { t: "z", f: "A3+1" } as XLSX.CellObject,
    });
    expect(ev.cell("S", 0, 0, "1/0").error).toBe("#DIV/0!");
    expect(ev.cell("S", 1, 0, "FOOBAR(1)").unsupported).toBe(true);
    expect(ev.cell("S", 2, 0, "A4+1").error).toBeTruthy();
  });
});

describe("formatValue", () => {
  it("dùng định dạng số của ô", () => {
    expect(formatValue(217950000, "#,##0")).toBe("217,950,000");
    expect(formatValue(0.125, "0.0%")).toBe("12.5%");
    expect(formatValue(1 / 3)).toBe("0.3333333333");
    expect(formatValue(null)).toBe("");
  });
});

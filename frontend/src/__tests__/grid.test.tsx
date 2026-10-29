import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as XLSX from "xlsx";
import { api } from "../api";
import { PreviewPane } from "../components/PreviewPane";
import type { OfficeFile } from "../types";

function workbookBytes(): ArrayBuffer {
  const ws = XLSX.utils.aoa_to_sheet([["Tháng", "Doanh thu"], [1, 100], [2, 150]]);
  ws["B4"] = { t: "n", f: "SUM(B2:B3)" };
  ws["!ref"] = "A1:B4";
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Doanh thu");
  return XLSX.write(wb, { type: "array", bookType: "xlsx" });
}

const file: OfficeFile = { id: "f1", name: "so.xlsx", kind: "xlsx", current_version: 1, versions: 1 } as unknown as OfficeFile;

function setup() {
  vi.spyOn(api, "outline").mockResolvedValue({ sheets: [{ name: "Doanh thu", charts: [] }] });
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(workbookBytes()));
  const editCells = vi.spyOn(api, "editCells").mockResolvedValue({ file, diff: { cells: [] }, summary: "" });
  const onSelect = vi.fn();
  const onEdited = vi.fn();
  render(<PreviewPane file={file} reloadKey={0} diff={undefined} selection={null} onSelect={onSelect}
    onUndo={() => {}} onRedo={() => {}} onHistory={() => {}} onEdited={onEdited} />);
  return { editCells, onSelect, onEdited };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("lưới Excel dùng bàn phím", () => {
  it("di chuyển bằng mũi tên, gõ để sửa, Enter lưu và xuống dòng", async () => {
    const { editCells, onEdited } = setup();
    const grid = await screen.findByRole("grid");
    const nameBox = screen.getByLabelText("Ô đang chọn");
    fireEvent.mouseDown(screen.getByText("Tháng"));
    expect(nameBox.textContent).toBe("A1");
    fireEvent.keyDown(grid, { key: "ArrowRight" });
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    expect(nameBox.textContent).toBe("B2");
    expect(grid.getAttribute("aria-activedescendant")).toBe("xl-B2");

    fireEvent.keyDown(grid, { key: "5" });
    const input = screen.getByLabelText("Sửa ô B2") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "500" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(editCells).toHaveBeenCalledWith("f1", "Doanh thu", [{ ref: "B2", value: "500" }]));
    await waitFor(() => expect(onEdited).toHaveBeenCalled());
    expect(nameBox.textContent).toBe("B3");
  });

  it("ô công thức hiện kết quả; F2 sửa đúng công thức; Esc huỷ không lưu", async () => {
    const { editCells } = setup();
    const grid = await screen.findByRole("grid");
    expect(screen.getByText("250")).toBeTruthy();
    fireEvent.mouseDown(screen.getByText("250"));
    fireEvent.keyDown(grid, { key: "F2" });
    const input = screen.getByLabelText("Sửa ô B4") as HTMLInputElement;
    expect(input.value).toBe("=SUM(B2:B3)");
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByLabelText("Sửa ô B4")).toBeNull();
    expect(editCells).not.toHaveBeenCalled();
  });

  it("Shift + mũi tên chọn vùng", async () => {
    const { onSelect } = setup();
    const grid = await screen.findByRole("grid");
    fireEvent.mouseDown(screen.getByText("100"));
    fireEvent.keyDown(grid, { key: "ArrowDown", shiftKey: true });
    expect(onSelect).toHaveBeenLastCalledWith({ file: "so.xlsx", sheet: "Doanh thu", range: "B2:B3" });
  });

  it("Delete xoá các ô có dữ liệu", async () => {
    const { editCells } = setup();
    const grid = await screen.findByRole("grid");
    fireEvent.mouseDown(screen.getByText("Tháng"));
    fireEvent.mouseUp(grid);
    fireEvent.keyDown(grid, { key: "Delete" });
    await waitFor(() => expect(editCells).toHaveBeenCalledWith("f1", "Doanh thu", [{ ref: "A1", value: null }]));
  });
});

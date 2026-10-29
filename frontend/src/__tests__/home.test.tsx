import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import type { BarProps } from "../components/TopBar";
import { HomePage } from "../pages/HomePage";
import { parseRoute } from "../router";
import type { ChatSession } from "../types";

const bar: BarProps = { theme: "dark", onToggleTheme: () => {}, settings: null, onOpenSettings: () => {} };

const sessions: ChatSession[] = [
  { id: "a1", title: "Doanh thu Q3", created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-20T08:00:00Z",
    kind: "xlsx", files: [{ id: "f1", name: "dt.xlsx", kind: "xlsx" }], message_count: 3,
    preview: { file_id: "f1", version: 4, kind: "xlsx" } },
  { id: "b2", title: "Hợp đồng dịch vụ", created_at: "2026-10-02T00:00:00Z", updated_at: "2026-10-10T08:00:00Z",
    kind: "docx", files: [{ id: "f2", name: "hd.docx", kind: "docx" }], message_count: 1, preview: null },
];

beforeEach(() => {
  location.hash = "#/";
  vi.spyOn(api, "listSessions").mockResolvedValue(sessions);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("HomePage", () => {
  it("cho chọn loại tệp để bắt đầu và liệt kê phiên gần đây", async () => {
    render(<HomePage bar={bar} onError={() => {}} />);
    for (const name of ["Bảng tính", "Tài liệu", "Bản trình chiếu", "Mở tệp có sẵn"])
      expect(screen.getByRole("button", { name: new RegExp(name) })).toBeTruthy();
    expect(await screen.findByText("Doanh thu Q3")).toBeTruthy();
    expect(screen.getByText("Hợp đồng dịch vụ")).toBeTruthy();
    // Ảnh xem trước là nội dung thật của tệp chính, cache theo phiên bản
    expect(document.querySelector(".session-thumb img")?.getAttribute("src")).toBe("/api/files/f1/thumbnail.png?v=4");
  });

  it("bấm Bảng tính → tạo phiên Excel rồi mở không gian làm việc", async () => {
    const create = vi.spyOn(api, "createSession").mockResolvedValue({ ...sessions[0], id: "new1" });
    render(<HomePage bar={bar} onError={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /^Bảng tính/ }));
    await waitFor(() => expect(location.hash).toBe("#/s/new1"));
    expect(create).toHaveBeenCalledWith("xlsx");
  });

  it("lọc theo loại tệp và tìm theo tên", async () => {
    render(<HomePage bar={bar} onError={() => {}} />);
    await screen.findByText("Doanh thu Q3");
    fireEvent.click(screen.getByRole("button", { name: "Word" }));
    expect(screen.queryByText("Doanh thu Q3")).toBeNull();
    expect(screen.getByText("Hợp đồng dịch vụ")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Tất cả" }));
    fireEvent.change(screen.getByLabelText("Tìm phiên hoặc tệp"), { target: { value: "dt.xlsx" } });
    expect(screen.getByText("Doanh thu Q3")).toBeTruthy();
    expect(screen.queryByText("Hợp đồng dịch vụ")).toBeNull();
  });

  it("xoá phiên phải xác nhận trước", async () => {
    const del = vi.spyOn(api, "deleteSession").mockResolvedValue();
    render(<HomePage bar={bar} onError={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: "Xoá phiên Doanh thu Q3" }));
    expect(del).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Xoá vĩnh viễn/ }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("a1"));
    await waitFor(() => expect(screen.queryByText("Doanh thu Q3")).toBeNull());
  });
});

describe("parseRoute", () => {
  it("nhận ra trang chủ và trang phiên", () => {
    expect(parseRoute("")).toEqual({ page: "home" });
    expect(parseRoute("#/")).toEqual({ page: "home" });
    expect(parseRoute("#/s/abc123")).toEqual({ page: "session", id: "abc123" });
  });
});

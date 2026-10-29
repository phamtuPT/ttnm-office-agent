import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatPanel, describeSelection, toBlocks } from "../components/ChatPanel";
import type { ChatItem } from "../types";

afterEach(cleanup);

const base = {
  sessionId: "s1",
  busy: false,
  connected: true,
  activeFile: "dt.xlsx",
  selection: null,
  onClearSelection: () => {},
  onCancel: () => {},
  onOpenFile: () => {},
  onError: () => {},
};

describe("toBlocks", () => {
  it("gom các bước tool liên tiếp thành một khối terminal", () => {
    const items: ChatItem[] = [
      { kind: "text", role: "user", text: "Tạo bảng" },
      { kind: "tool", id: "1", name: "excel_create_workbook", args: {}, status: "ok" },
      { kind: "tool", id: "2", name: "excel_add_chart", args: {}, status: "running" },
      { kind: "text", role: "model", text: "Xong" },
    ];
    const blocks = toBlocks(items);
    expect(blocks.map((b) => b.kind)).toEqual(["text", "tools", "text"]);
    expect(blocks[1].kind === "tools" && blocks[1].items.length).toBe(2);
  });
});

describe("describeSelection", () => {
  it("mô tả vùng chọn theo loại tệp (đánh số từ 1 cho người dùng)", () => {
    expect(describeSelection({ file: "a.xlsx", sheet: "S", range: "B2:D10" })).toBe("a.xlsx › S!B2:D10");
    expect(describeSelection({ file: "a.docx", paragraphs: [0, 2] })).toBe("a.docx › đoạn 1, 3");
    expect(describeSelection({ file: "a.pptx", slides: [1] })).toBe("a.pptx › slide 2");
  });
});

describe("ChatPanel", () => {
  it("không cho gửi khi ô soạn trống; Enter gửi, Shift+Enter không gửi", () => {
    const onSend = vi.fn();
    render(<ChatPanel {...base} items={[]} onSend={onSend} />);
    const send = screen.getByRole("button", { name: /Gửi/ });
    expect(send).toHaveProperty("disabled", true);

    const box = screen.getByLabelText("Yêu cầu");
    fireEvent.change(box, { target: { value: "Tô đỏ giá trị âm" } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("Tô đỏ giá trị âm", []);
  });

  it("đang xử lý thì hiện nút Dừng thay cho Gửi", () => {
    const onCancel = vi.fn();
    render(<ChatPanel {...base} busy items={[]} onSend={() => {}} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole("button", { name: "Dừng" }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("hiện dòng kế hoạch, nhật ký tool có nhãn tiếng Việt và lỗi tool", () => {
    const items: ChatItem[] = [
      { kind: "text", role: "model", text: "① Đọc bảng → ② Ghi tổng\nĐang làm" },
      { kind: "tool", id: "1", name: "excel_write_cells", args: {}, status: "error", result: { error: "Ô nằm ngoài vùng" } },
    ];
    render(<ChatPanel {...base} items={items} onSend={() => {}} />);
    expect(screen.getByText("① Đọc bảng → ② Ghi tổng")).toBeTruthy();
    expect(screen.getByText("Ghi ô")).toBeTruthy();
    expect(screen.getByText(/Ô nằm ngoài vùng/)).toBeTruthy();
  });

  it("hiển thị Markdown trong trả lời (không còn dấu **), bỏ qua HTML thô", () => {
    const items: ChatItem[] = [{ kind: "text", role: "model", text:
      "Đã tạo **Bảng tính mới.xlsx**:\n\n- Vùng `A1:E12`\n- Dòng **Tổng cộng** dùng `=SUM(E2:E11)`\n\n<img src=x onerror=alert(1)>" }];
    const { container } = render(<ChatPanel {...base} items={items} onSend={() => {}} />);
    expect(container.querySelector(".msg.model strong")?.textContent).toBe("Bảng tính mới.xlsx");
    expect(container.querySelectorAll(".msg.model li").length).toBe(2);
    expect(container.querySelector(".msg.model code")?.textContent).toBe("A1:E12");
    expect(container.querySelector(".msg.model")?.textContent).not.toContain("**");
    expect(container.querySelector(".msg.model img")).toBeNull();
  });

});

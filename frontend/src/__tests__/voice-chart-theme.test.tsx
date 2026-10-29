import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import * as XLSX from "xlsx";
import { afterEach, describe, expect, it, vi } from "vitest";
import { readRange } from "../components/ChartView";
import { loadTheme } from "../theme";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("VoiceButton", () => {
  it("dùng Web Speech API: chữ đang nghe hiện tạm, chữ đã chốt đưa vào ô soạn, không tự gửi", async () => {
    let instance: any;
    class FakeRecognition {
      lang = ""; interimResults = false; continuous = false;
      onresult: any; onerror: any; onend: any;
      constructor() { instance = this; }
      start() {}
      stop() { this.onend?.(); }
      abort() {}
    }
    vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
    const { VoiceButton } = await import("../components/VoiceButton");
    const onFinal = vi.fn();
    const onInterim = vi.fn();
    render(<VoiceButton sessionId="s" onFinal={onFinal} onInterim={onInterim} onError={() => {}} />);
    fireEvent.click(screen.getByRole("button"));
    expect(instance.lang).toBe("vi-VN");
    act(() => instance.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: "tô đỏ" }], { isFinal: false })] }));
    expect(onInterim).toHaveBeenLastCalledWith("tô đỏ");
    act(() => instance.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: "tô đỏ ô âm " }], { isFinal: true })] }));
    expect(onFinal).toHaveBeenCalledWith("tô đỏ ô âm");
    expect(screen.getByRole("button").getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("button").getAttribute("aria-pressed")).toBe("false");
  });

  it("báo lỗi dễ hiểu khi bị từ chối quyền micro", async () => {
    let instance: any;
    class FakeRecognition {
      onresult: any; onerror: any; onend: any;
      constructor() { instance = this; }
      start() {}
      stop() {}
      abort() {}
    }
    vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
    const { VoiceButton } = await import("../components/VoiceButton");
    const onError = vi.fn();
    render(<VoiceButton sessionId="s" onFinal={() => {}} onInterim={() => {}} onError={onError} />);
    fireEvent.click(screen.getByRole("button"));
    act(() => instance.onerror({ error: "not-allowed" }));
    expect(onError.mock.calls[0][0]).toMatch(/quyền micro/);
  });

  it("trình duyệt không có Web Speech API và không có micro → báo lỗi, gợi ý gõ", async () => {
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: () => Promise.reject(new Error("no")) } });
    const { VoiceButton } = await import("../components/VoiceButton");
    const onError = vi.fn();
    render(<VoiceButton sessionId="s" onFinal={() => {}} onInterim={() => {}} onError={onError} />);
    await act(async () => fireEvent.click(screen.getByRole("button")));
    expect(onError.mock.calls[0][0]).toMatch(/gõ yêu cầu/);
  });
});

describe("readRange (biểu đồ SVG)", () => {
  it("đọc giá trị theo tham chiếu có tên sheet, ô công thức chưa tính → null", () => {
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet([["Tháng", "DT"], [1, 10], [2, 20]]);
    ws["B4"] = { t: "z", f: "SUM(B2:B3)" } as any;
    ws["!ref"] = "A1:B4";
    XLSX.utils.book_append_sheet(wb, ws, "Doanh thu");
    expect(readRange(wb, "'Doanh thu'!$B$2:$B$3", "x")).toEqual([10, 20]);
    expect(readRange(wb, "B2:B4", "Doanh thu")).toEqual([10, 20, null]);
    expect(readRange(wb, null, "Doanh thu")).toEqual([]);
  });
});

describe("loadTheme", () => {
  it("không lỗi khi trình duyệt chặn localStorage", () => {
    vi.stubGlobal("localStorage", { getItem: () => { throw new Error("blocked"); } });
    expect(["dark", "light"]).toContain(loadTheme());
  });
});

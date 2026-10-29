import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import type { BarProps } from "../components/TopBar";
import { AuthPage } from "../pages/AuthPage";
import { SusPage } from "../pages/SusPage";

const bar: BarProps = { theme: "light", onToggleTheme: () => {}, settings: null, onOpenSettings: () => {} };

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("đăng nhập", () => {
  it("đăng nhập gọi API rồi báo người dùng; lỗi hiện thông báo", async () => {
    const user = { id: "u1", email: "an@vi.du", name: "An", is_admin: true };
    const login = vi.spyOn(api, "login").mockRejectedValueOnce(new Error("Email hoặc mật khẩu không đúng")).mockResolvedValue(user);
    const onDone = vi.fn();
    render(<AuthPage canRegister onDone={onDone} />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "an@vi.du" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "sai" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect((await screen.findByRole("alert")).textContent).toContain("không đúng");
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(user));
    expect(login).toHaveBeenCalledWith("an@vi.du", "sai");
    fireEvent.click(screen.getByRole("button", { name: /Tạo tài khoản$/ }));
    expect(screen.getByLabelText("Tên hiển thị")).toBeTruthy();
  });
});

describe("phiếu SUS", () => {
  it("phải chọn đủ 10 câu mới gửi được, gửi xong hiện điểm", async () => {
    vi.spyOn(api, "susQuestions").mockResolvedValue({
      questions: Array.from({ length: 10 }, (_, i) => `Câu hỏi ${i + 1}`),
      scale: ["Hoàn toàn không đồng ý", "Không đồng ý", "Trung lập", "Đồng ý", "Hoàn toàn đồng ý"],
    });
    const submit = vi.spyOn(api, "submitSus").mockResolvedValue({ id: "r1", score: 82.5 });
    render(<SusPage bar={bar} onError={() => {}} />);
    await screen.findAllByText("Câu hỏi 1"); // legend (cho trình đọc màn hình) + chữ hiển thị
    const send = screen.getByRole("button", { name: /Gửi phiếu/ }) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    const answers = [4, 2, 4, 1, 5, 2, 4, 2, 4, 1];
    answers.forEach((v, i) => fireEvent.click(screen.getAllByRole("radio", { name: new RegExp(`^${v} —`) })[i]));
    expect(send.disabled).toBe(false);
    fireEvent.click(send);
    await waitFor(() => expect(submit).toHaveBeenCalledWith(answers, "", ""));
    expect(await screen.findByText("82.5")).toBeTruthy();
  });
});

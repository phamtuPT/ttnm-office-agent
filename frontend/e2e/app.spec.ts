import { expect, type Page, test } from "@playwright/test";

// Luồng chính của người dùng trên ứng dụng thật (backend dùng trợ lý giả: "tạo bảng", "hoàn tác").

async function newSession(page: Page, kind: "Bảng tính" | "Tài liệu" | "Bản trình chiếu") {
  await page.goto("/");
  await page.getByRole("button", { name: new RegExp(`^${kind}`) }).click();
  await expect(page).toHaveURL(/#\/s\/[0-9a-f]{32}$/);
  await expect(page.getByRole("textbox", { name: "Yêu cầu" })).toBeVisible();
}

async function ask(page: Page, text: string) {
  const box = page.getByRole("textbox", { name: "Yêu cầu" });
  await box.fill(text);
  await box.press("Enter");
}

test("giao việc cho trợ lý: kế hoạch nhiều bước, bảng có công thức, biểu đồ gốc", async ({ page }) => {
  await newSession(page, "Bảng tính");
  await ask(page, "tạo bảng doanh thu 12 tháng");

  await expect(page.getByText(/① Tạo bảng/)).toBeVisible(); // kế hoạch nhiều bước
  await expect(page.getByText(/\(mock\) Đã tạo mock-doanh-thu/)).toBeVisible();
  await expect(page.getByRole("button", { name: /mock-doanh-thu/ }).first()).toBeVisible();

  // Lưới hiện KẾT QUẢ công thức =SUM(B2:B13), công thức gốc nằm trên thanh công thức
  const grid = page.getByRole("grid");
  await expect(grid.getByRole("gridcell", { name: "1980" })).toBeVisible();
  await grid.getByRole("gridcell", { name: "1980" }).click();
  await expect(page.getByLabel("Thanh công thức")).toContainText("=SUM(B2:B13)");

  // Biểu đồ gốc gắn với vùng ô được vẽ lại trong khung xem trước
  await expect(page.getByLabel("Biểu đồ trong sheet")).toContainText("Doanh thu theo tháng");
});

test("sửa ô trực tiếp bằng bàn phím: gõ, Enter lưu, công thức tự tính, Delete xoá", async ({ page }) => {
  await newSession(page, "Bảng tính");
  const grid = page.getByRole("grid");
  await grid.locator("#xl-A1").click();
  await page.keyboard.type("Doanh thu");
  await page.keyboard.press("Enter");
  await expect(grid.locator("#xl-A1")).toHaveText("Doanh thu");
  await expect(page.getByLabel("Ô đang chọn", { exact: true })).toHaveText("A2");

  await page.keyboard.type("=LEN(A1)*2");
  await page.keyboard.press("Enter");
  await expect(grid.locator("#xl-A2")).toHaveText("18");

  // Mỗi lần sửa là một phiên bản; Hoàn tác trên tệp trả lại phiên bản trước
  await expect(page.locator(".file-tab.active")).toContainText("v3");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Delete");
  await expect(grid.locator("#xl-A2")).toHaveText("");
  await page.getByRole("button", { name: "Hoàn tác", exact: true }).click();
  await expect(grid.locator("#xl-A2")).toHaveText("18");
});

test("tab phiên trên thanh cửa sổ, phiên gần đây ở trang chủ, xoá phiên có xác nhận", async ({ page }) => {
  await newSession(page, "Tài liệu");
  const tabs = page.getByRole("navigation", { name: "Trang đang mở" });
  await expect(tabs.getByRole("link", { name: /Tài liệu mới/ })).toHaveAttribute("aria-current", "page");

  await tabs.getByRole("link", { name: /Trang chủ/ }).click();
  await expect(page.getByRole("heading", { name: "Bắt đầu làm việc mới" })).toBeVisible();
  const card = page.getByRole("button", { name: /Xoá phiên Tài liệu mới/ }).first();
  await expect(card).toBeVisible();
  const before = await page.getByRole("button", { name: /^Xoá phiên/ }).count();
  await card.click();
  await page.getByRole("button", { name: /Xoá vĩnh viễn/ }).click();
  await expect(page.getByRole("button", { name: /^Xoá phiên/ })).toHaveCount(before - 1);
});

test("trợ lý trả lời bằng Markdown, không còn ký hiệu ** thô", async ({ page }) => {
  await newSession(page, "Bản trình chiếu");
  await ask(page, "xin chào");
  const reply = page.getByText(/\(mock\) Bạn vừa nói/);
  await expect(reply).toBeVisible();
  await expect(reply).not.toContainText("**");
});

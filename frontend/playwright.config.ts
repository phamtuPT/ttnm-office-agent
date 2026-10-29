import os from "node:os";
import path from "node:path";
import { defineConfig } from "@playwright/test";

// Test end-to-end: tự chạy backend riêng (trợ lý giả, SQLite + thư mục tạm, không đụng dữ liệu thật) và Vite riêng.
//   npx playwright test                 → dùng Edge/Chrome có sẵn trên máy (không cần tải trình duyệt)
//   E2E_CHANNEL=chromium npx playwright test   → dùng Chromium của Playwright (CI: npx playwright install chromium)
const BACKEND_PORT = 8031;
const FRONTEND_PORT = 5181;
const storage = path.join(os.tmpdir(), `office-agent-e2e-${process.pid}`);
const python = path.join("..", "backend", ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const channel = process.env.E2E_CHANNEL ?? (process.platform === "win32" ? "msedge" : "chrome");

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false, // cùng một backend: chạy lần lượt cho dễ đọc lỗi
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    channel: channel === "chromium" ? undefined : channel,
    locale: "vi-VN",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --port ${BACKEND_PORT}`,
      cwd: path.join("..", "backend"),
      url: `http://localhost:${BACKEND_PORT}/api/settings`,
      env: { LLM_PROVIDER: "mock", DATABASE_URL: "", STORAGE_DIR: storage, PII_MASKING: "false", SANDBOX_URL: "" },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx vite --port ${FRONTEND_PORT} --strictPort`,
      url: `http://localhost:${FRONTEND_PORT}`,
      env: { BACKEND_URL: `http://localhost:${BACKEND_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});

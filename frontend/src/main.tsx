import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Font tự host (không gọi Google Fonts) — chạy được khi offline và không lộ IP người dùng.
// Anybody cho tiêu đề/nút/nhãn, Be Vietnam Pro cho nội dung; mã và nhật ký dùng monospace hệ thống.
import "@fontsource/be-vietnam-pro/vietnamese-400.css";
import "@fontsource/be-vietnam-pro/vietnamese-500.css";
import "@fontsource/be-vietnam-pro/vietnamese-600.css";
import "@fontsource/be-vietnam-pro/latin-400.css";
import "@fontsource/be-vietnam-pro/latin-500.css";
import "@fontsource/be-vietnam-pro/latin-600.css";
import "@fontsource-variable/anybody";
import App from "./App";
import "./styles.css";
import { applyTheme, loadTheme } from "./theme";

applyTheme(loadTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

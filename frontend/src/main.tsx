import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Font Inter Tight tự host (không gọi Google Fonts) — chạy được khi offline và không lộ IP người dùng.
// Bản variable có đủ độ đậm 100–900 và bộ ký tự tiếng Việt; mã và nhật ký dùng monospace hệ thống.
import "@fontsource-variable/inter-tight";
import App from "./App";
import "./styles.css";
import { applyTheme, loadTheme } from "./theme";

applyTheme(loadTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

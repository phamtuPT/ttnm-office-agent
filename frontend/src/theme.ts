export type Theme = "dark" | "light";

const KEY = "office-agent-theme";

/** Giao diện đã chọn; mặc định theo hệ điều hành. localStorage có thể bị chặn → bỏ qua. */
export function loadTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    /* trình duyệt chặn lưu trữ */
  }
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem(KEY, t);
  } catch {
    /* bỏ qua */
  }
}

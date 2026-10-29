export type Theme = "dark" | "light";

const KEY = "office-agent-theme";

/** Giao diện đã chọn; mặc định sáng. localStorage có thể bị chặn → bỏ qua. */
export function loadTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    /* trình duyệt chặn lưu trữ */
  }
  return "light"; // giao diện sáng là mặc định, người dùng đổi bằng nút sáng/tối
}

export function applyTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem(KEY, t);
  } catch {
    /* bỏ qua */
  }
}

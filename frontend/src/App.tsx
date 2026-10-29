import { AlertTriangle, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "./api";
import { SettingsDialog } from "./components/SettingsDialog";
import type { BarProps } from "./components/TopBar";
import { HomePage } from "./pages/HomePage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { useRoute } from "./router";
import { applyTheme, loadTheme, type Theme } from "./theme";
import type { AppSettings } from "./types";

/** Khung ứng dụng: định tuyến trang chủ / không gian làm việc, giao diện sáng-tối, cài đặt AI, thông báo lỗi. */
export default function App() {
  const route = useRoute();
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => applyTheme(theme), [theme]);
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 8000); // thông báo tự ẩn, không đọng lại khi chuyển trang
    return () => clearTimeout(t);
  }, [error]);
  useEffect(() => {
    api.getSettings().then(setSettings).catch(() => {});
  }, []);

  const bar: BarProps = {
    theme,
    onToggleTheme: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    settings,
    onOpenSettings: () => setShowSettings(true),
  };

  return (
    <>
      {route.page === "home"
        ? <HomePage bar={bar} onError={setError} />
        : <WorkspacePage key={route.id} sessionId={route.id} bar={bar} onError={setError} />}

      {error && (
        <div className="toast" role="alert">
          <AlertTriangle size={18} className="toast-icon" aria-hidden />
          <span>{error}</span>
          <button onClick={() => setError(null)} aria-label="Đóng thông báo"><X size={16} aria-hidden /></button>
        </div>
      )}
      {showSettings && <SettingsDialog onClose={() => setShowSettings(false)} onSaved={setSettings} onError={setError} />}
    </>
  );
}

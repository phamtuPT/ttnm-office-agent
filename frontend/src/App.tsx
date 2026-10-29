import { AlertTriangle, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, UNAUTHORIZED_EVENT } from "./api";
import { SettingsDialog } from "./components/SettingsDialog";
import type { BarProps } from "./components/TopBar";
import { AuthPage } from "./pages/AuthPage";
import { HomePage } from "./pages/HomePage";
import { SusPage, SusResultsPage } from "./pages/SusPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { useRoute } from "./router";
import { applyTheme, loadTheme, type Theme } from "./theme";
import type { AppSettings, AuthState } from "./types";

/** Khung ứng dụng: định tuyến trang chủ / không gian làm việc, giao diện sáng-tối, cài đặt AI, thông báo lỗi. */
export default function App() {
  const route = useRoute();
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [auth, setAuth] = useState<AuthState | null>(null);

  useEffect(() => applyTheme(theme), [theme]);
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 8000); // thông báo tự ẩn, không đọng lại khi chuyển trang
    return () => clearTimeout(t);
  }, [error]);
  useEffect(() => {
    api.me().then(setAuth).catch(() => setAuth({ enabled: false, user: null, can_register: false }));
    // Phiên đăng nhập hết hạn giữa chừng → quay về trang đăng nhập
    const expired = () => setAuth((a) => (a?.enabled ? { ...a, user: null } : a));
    window.addEventListener(UNAUTHORIZED_EVENT, expired);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, expired);
  }, []);
  const signedIn = !!auth && (!auth.enabled || !!auth.user);
  useEffect(() => {
    if (signedIn) api.getSettings().then(setSettings).catch(() => {});
  }, [signedIn, auth?.user?.id]);

  const bar: BarProps = {
    theme,
    onToggleTheme: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    settings,
    onOpenSettings: () => setShowSettings(true),
    user: auth?.user,
    onLogout: async () => {
      await api.logout();
      setAuth((a) => (a ? { ...a, user: null } : a));
    },
  };

  if (!auth) return null;
  if (!signedIn) return <AuthPage canRegister={auth.can_register} onDone={(u) => setAuth({ ...auth, user: u })} />;

  return (
    <>
      {route.page === "home" && <HomePage bar={bar} onError={setError} />}
      {route.page === "session" && <WorkspacePage key={route.id} sessionId={route.id} bar={bar} onError={setError} />}
      {route.page === "sus" && <SusPage bar={bar} onError={setError} />}
      {route.page === "sus-results" && <SusResultsPage bar={bar} onError={setError} />}

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

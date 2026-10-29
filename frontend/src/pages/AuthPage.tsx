import { LogIn, UserPlus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api } from "../api";
import { Logo } from "../components/icons";
import type { AuthUser } from "../types";

/** Đăng nhập / đăng ký — chỉ hiện khi máy chủ bật AUTH_ENABLED (nhiều người dùng chung). */
export function AuthPage({ canRegister, onDone }: { canRegister: boolean; onDone: (u: AuthUser) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onDone(mode === "login" ? await api.login(email, password) : await api.register(email, name, password));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="app auth">
      <div className="surface auth-surface">
        <form className="auth-card" onSubmit={submit} aria-labelledby="auth-title">
          <div className="logo"><Logo /><span className="logo-text">office<span className="dotc">.</span>agent</span></div>
          <h1 id="auth-title" className="title">{mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}</h1>
          <p className="muted">Mỗi người chỉ thấy phiên làm việc và tệp của mình.</p>
          {mode === "register" && (
            <label className="field">Tên hiển thị
              <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={100} />
            </label>
          )}
          <label className="field">Email
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </label>
          <label className="field">Mật khẩu
            <input type="password" required minLength={mode === "register" ? 8 : 1} value={password}
              onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} />
          </label>
          {mode === "register" && <small className="muted">Tối thiểu 8 ký tự.</small>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="btn solid" type="submit" disabled={busy}>
            {mode === "login" ? <LogIn size={16} aria-hidden /> : <UserPlus size={16} aria-hidden />}
            {mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}
          </button>
          {canRegister && (
            <button type="button" className="link-btn" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
              {mode === "login" ? "Chưa có tài khoản? Tạo tài khoản" : "Đã có tài khoản? Đăng nhập"}
            </button>
          )}
        </form>
      </div>
    </div>
  );
}

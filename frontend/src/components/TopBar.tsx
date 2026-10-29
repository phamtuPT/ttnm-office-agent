import { Cpu, Moon, Sun } from "lucide-react";
import type { ReactNode } from "react";
import type { Theme } from "../theme";
import type { AppSettings } from "../types";
import { Logo } from "./icons";

export const PROVIDER_LABEL: Record<string, string> = { gemini: "Gemini", openai: "OpenAI", ollama: "Ollama", mock: "Thử nghiệm" };

export interface BarProps {
  theme: Theme;
  onToggleTheme: () => void;
  settings: AppSettings | null;
  onOpenSettings: () => void;
}

/** Thanh trên cùng: logo + phần riêng của từng trang ở giữa + mô hình AI và sáng/tối bên phải. */
export function TopBar({ bar, left, right, connected = true }: { bar: BarProps; left?: ReactNode; right?: ReactNode; connected?: boolean }) {
  const { settings } = bar;
  return (
    <header className="topbar">
      {left}
      <a className="brand" href="#/" aria-label="Về trang chủ">
        <Logo />
        <span className="brand-name">office<span className="dotc">.</span>agent</span>
      </a>
      <span className="spacer" />
      {right}
      <button className="btn" onClick={bar.onOpenSettings} title="Đổi mô hình AI">
        <Cpu size={16} aria-hidden />
        <span className={`dot ${connected ? "" : "off"}`} aria-hidden />
        <span className="label-wide">{settings ? PROVIDER_LABEL[settings.provider] : "…"}</span>
        {settings?.pii_masking && <span className="pill ok" title="Đang che thông tin cá nhân trước khi gửi lên đám mây">PII</span>}
      </button>
      <button className="btn icon" onClick={bar.onToggleTheme}
        aria-label={bar.theme === "dark" ? "Chuyển giao diện sáng" : "Chuyển giao diện tối"} title="Đổi sáng/tối">
        {bar.theme === "dark" ? <Sun size={17} aria-hidden /> : <Moon size={17} aria-hidden />}
      </button>
    </header>
  );
}

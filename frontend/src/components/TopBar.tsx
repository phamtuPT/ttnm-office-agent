import { Cpu, House, Moon, Plus, Sun, X } from "lucide-react";
import type { ReactNode } from "react";
import { closeTab, useOpenTabs } from "../openTabs";
import { navigate } from "../router";
import type { Theme } from "../theme";
import type { AppSettings } from "../types";
import { FileKindIcon, Logo } from "./icons";

export const PROVIDER_LABEL: Record<string, string> = { gemini: "Gemini", openai: "OpenAI", ollama: "Ollama", mock: "Thử nghiệm" };

export interface BarProps {
  theme: Theme;
  onToggleTheme: () => void;
  settings: AppSettings | null;
  onOpenSettings: () => void;
}

/**
 * Thanh cửa sổ: logo, dải tab (Trang chủ + các phiên đang mở, tab đang xem "liền" với nội dung bên dưới),
 * phần riêng của từng trang, mô hình AI và nút sáng/tối.
 */
export function TopBar({ bar, activeId, right, connected = true }: {
  bar: BarProps; activeId: string | null; right?: ReactNode; connected?: boolean;
}) {
  const tabs = useOpenTabs();
  const { settings } = bar;

  const close = (id: string) => {
    closeTab(id);
    if (id === activeId) navigate({ page: "home" });
  };

  return (
    <header className="wbar">
      <a className="logo" href="#/" aria-label="Office Agent — trang chủ">
        <Logo />
        <span className="logo-text">office<span className="dotc">.</span>agent</span>
      </a>
      <nav className="wtabs" aria-label="Trang đang mở">
        <a className={`wtab ${activeId === null ? "on" : ""}`} href="#/" aria-current={activeId === null ? "page" : undefined}>
          <House size={15} aria-hidden /> <span className="t">Trang chủ</span>
        </a>
        {tabs.map((t) => (
          <a key={t.id} className={`wtab ${t.id === activeId ? "on" : ""}`} href={`#/s/${t.id}`}
            aria-current={t.id === activeId ? "page" : undefined} title={t.title}>
            <FileKindIcon kind={t.kind} size={15} />
            <span className="t">{t.title}</span>
            <button className="x" aria-label={`Đóng tab ${t.title}`}
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); close(t.id); }}>
              <X size={12} aria-hidden />
            </button>
          </a>
        ))}
        <button className="circle-btn" onClick={() => navigate({ page: "home" })} aria-label="Bắt đầu phiên mới" title="Bắt đầu phiên mới">
          <Plus size={16} aria-hidden />
        </button>
      </nav>
      <span className="spacer" />
      {right}
      <button className="btn" onClick={bar.onOpenSettings} title="Đổi mô hình AI">
        <Cpu size={16} aria-hidden />
        <span className={`dot ${connected ? "" : "off"}`} aria-hidden />
        <span className="label-wide">{settings ? PROVIDER_LABEL[settings.provider] : "…"}</span>
        {settings?.pii_masking && <span className="pill ok" title="Đang che thông tin cá nhân trước khi gửi lên đám mây">PII</span>}
      </button>
      <button className="circle-btn" onClick={bar.onToggleTheme}
        aria-label={bar.theme === "dark" ? "Chuyển giao diện sáng" : "Chuyển giao diện tối"} title="Đổi sáng/tối">
        {bar.theme === "dark" ? <Sun size={16} aria-hidden /> : <Moon size={16} aria-hidden />}
      </button>
    </header>
  );
}

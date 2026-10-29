import { useEffect, useState } from "react";
import { api } from "../api";
import type { AppSettings, Provider } from "../types";

const PROVIDERS: { id: Provider; label: string; note: string }[] = [
  { id: "gemini", label: "Google Gemini", note: "Đám mây, đọc ảnh tốt. Cần khoá API." },
  { id: "openai", label: "OpenAI", note: "Đám mây. Cần khoá API." },
  { id: "ollama", label: "Ollama", note: "Chạy trên máy (hoặc Ollama cloud) — dữ liệu không rời máy." },
  { id: "mock", label: "Thử nghiệm", note: "Trợ lý giả, không gọi AI — để thử giao diện." },
];

/** Đổi nhà cung cấp/model ngay khi đang chạy. Khoá API chỉ nhập, không bao giờ hiển thị lại. */
export function SettingsDialog(p: { onClose: () => void; onSaved: (s: AppSettings) => void; onError: (m: string) => void }) {
  const [s, setS] = useState<AppSettings | null>(null);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getSettings().then(setS).catch((e) => p.onError(e.message));
  }, []);

  if (!s) return null;
  const m = s.models[s.provider];
  const setModel = (k: "agent" | "lite", v: string) =>
    setS({ ...s, models: { ...s.models, [s.provider]: { ...m, [k]: v } } });

  const save = async () => {
    setSaving(true);
    try {
      const api_keys = Object.fromEntries(Object.entries(keys).filter(([, v]) => v.trim()));
      const saved = await api.saveSettings({
        provider: s.provider, models: s.models, ollama_base_url: s.ollama_base_url, pii_masking: s.pii_masking,
        ...(Object.keys(api_keys).length ? { api_keys } : {}),
      });
      p.onSaved(saved);
      p.onClose();
    } catch (e) {
      p.onError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const keyProvider = s.provider === "gemini" || s.provider === "openai" ? s.provider : null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="set-title" onClick={p.onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3 id="set-title">Cài đặt mô hình AI</h3>
        <fieldset className="providers">
          <legend>Nhà cung cấp</legend>
          {PROVIDERS.map((x) => (
            <label key={x.id} className={s.provider === x.id ? "active" : ""}>
              <input type="radio" name="provider" checked={s.provider === x.id} onChange={() => setS({ ...s, provider: x.id })} />
              <span><b>{x.label}</b><small>{x.note}</small></span>
            </label>
          ))}
        </fieldset>

        {s.provider !== "mock" && (
          <div className="form">
            <label>Model chính
              <input value={m?.agent ?? ""} onChange={(e) => setModel("agent", e.target.value)}
                placeholder={s.provider === "ollama" ? "ví dụ: qwen3, gpt-oss" : ""} />
            </label>
            <label>Model phụ (đặt tên phiên…)
              <input value={m?.lite ?? ""} onChange={(e) => setModel("lite", e.target.value)} placeholder="để trống = dùng model chính" />
            </label>
            {s.provider === "ollama" && (
              <label>Địa chỉ Ollama
                <input value={s.ollama_base_url} onChange={(e) => setS({ ...s, ollama_base_url: e.target.value })} />
              </label>
            )}
            {keyProvider && (
              <label>Khoá API {s.has_key[keyProvider] ? <span className="pill ok">đã lưu</span> : <span className="pill warn">chưa có</span>}
                <input type="password" autoComplete="off" value={keys[keyProvider] ?? ""}
                  onChange={(e) => setKeys({ ...keys, [keyProvider]: e.target.value })}
                  placeholder={s.has_key[keyProvider] ? "để trống = giữ khoá đã lưu" : "dán khoá API"} />
              </label>
            )}
            {s.provider !== "ollama" && (
              <label className="check">
                <input type="checkbox" checked={s.pii_masking} onChange={(e) => setS({ ...s, pii_masking: e.target.checked })} />
                Che email, số điện thoại, số thẻ, đường dẫn trước khi gửi lên đám mây
              </label>
            )}
          </div>
        )}
        {s.render_available === false && (
          <p className="hint">Máy chủ chưa cài LibreOffice: slide hiển thị dạng dàn ý và trợ lý không tự kiểm tra bố cục bằng hình ảnh.</p>
        )}
        <div className="modal-actions">
          <button className="btn" onClick={p.onClose}>Huỷ</button>
          <button className="btn primary" onClick={save} disabled={saving}>{saving ? "Đang lưu…" : "Lưu"}</button>
        </div>
      </div>
    </div>
  );
}

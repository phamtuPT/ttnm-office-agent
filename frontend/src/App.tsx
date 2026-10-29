import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { ChatPanel } from "./components/ChatPanel";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { FileList } from "./components/FileList";
import { Hero } from "./components/Hero";
import { HistoryDialog } from "./components/HistoryDialog";
import { PreviewPane } from "./components/PreviewPane";
import { SettingsDialog } from "./components/SettingsDialog";
import { applyTheme, loadTheme, type Theme } from "./theme";
import type { AppSettings, ChatSession, FileDiff, OfficeFile, Selection } from "./types";
import { useChatSocket } from "./useChatSocket";

export const PROVIDER_LABEL: Record<string, string> = { gemini: "Gemini", openai: "OpenAI", ollama: "Ollama", mock: "Thử nghiệm" };

export default function App() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [files, setFiles] = useState<OfficeFile[]>([]);
  const [fileId, setFileId] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [diffs, setDiffs] = useState<Record<string, FileDiff>>({});
  const [error, setError] = useState<string | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [dialog, setDialog] = useState<"settings" | "history" | null>(null);
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const [prefill, setPrefill] = useState<{ text: string; nonce: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  const refreshFiles = useCallback(async (sid: string) => {
    const fs = await api.listFiles(sid);
    setFiles(fs);
    setFileId((cur) => (cur && fs.some((f) => f.id === cur) ? cur : fs[0]?.id ?? null));
  }, []);

  const booted = useRef(false);
  useEffect(() => {
    if (booted.current) return; // StrictMode chạy effect hai lần → tránh tạo hai phiên rỗng
    booted.current = true;
    api.listSessions().then(async (ss) => {
      if (ss.length === 0) ss = [await api.createSession()];
      setSessions(ss);
      setSessionId(ss[0].id);
    }).catch((e) => setError(`Không kết nối được máy chủ: ${e.message}`));
    api.getSettings().then(setSettings).catch(() => {});
  }, []);

  useEffect(() => applyTheme(theme), [theme]);

  useEffect(() => {
    if (!sessionId) return;
    setSelection(null);
    setDiffs({});
    setFileId(null);
    refreshFiles(sessionId);
  }, [sessionId, refreshFiles]);

  const chat = useChatSocket(sessionId, {
    onFileChanged: (fid, diff) => {
      setDiffs((d) => ({ ...d, [fid]: diff }));
      setFileId(fid);
      setReloadKey((k) => k + 1);
      if (sessionId) refreshFiles(sessionId);
    },
    onTitle: (title) => setSessions((ss) => ss.map((s) => (s.id === sessionId ? { ...s, title } : s))),
    onError: setError,
  });

  const upload = async (list: FileList) => {
    if (!sessionId) return;
    for (const f of Array.from(list)) {
      try {
        const up = await api.uploadFile(sessionId, f);
        setFileId(up.id);
      } catch (e) {
        setError(`${f.name}: ${(e as Error).message}`);
      }
    }
    refreshFiles(sessionId);
  };

  const afterVersionChange = (fids: string[]) => {
    setDiffs((d) => ({ ...d, ...Object.fromEntries(fids.map((id) => [id, {}])) }));
    setReloadKey((k) => k + 1);
    if (sessionId) refreshFiles(sessionId);
  };

  const versionAction = async (fn: (id: string) => Promise<OfficeFile>) => {
    if (!fileId) return;
    try {
      await fn(fileId);
      afterVersionChange([fileId]);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const undoLastRequest = async () => {
    if (!sessionId) return;
    try {
      const fs = await api.undoLastRequest(sessionId);
      afterVersionChange(fs.map((f) => f.id));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const newSession = async () => {
    const s = await api.createSession();
    setSessions((ss) => [s, ...ss]);
    setSessionId(s.id);
  };

  const file = files.find((f) => f.id === fileId);
  const providerLabel = settings ? PROVIDER_LABEL[settings.provider] : "…";
  const hasDraggedFiles = (e: React.DragEvent) => Array.from(e.dataTransfer.types).includes("Files");

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand" aria-label="Office Agent">
          <span className="brand-mark" aria-hidden>OA</span>
          <span><span className="brand-name">office<span className="dotc">.</span>agent</span><span className="brand-sub">multimodal office ai · v0.4</span></span>
        </div>
        <select className="session-select" value={sessionId ?? ""} onChange={(e) => setSessionId(e.target.value)} aria-label="Phiên làm việc">
          {sessions.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
        </select>
        <button className="btn icon" onClick={newSession} title="Phiên mới" aria-label="Phiên mới">＋</button>
        <span className="spacer" />
        <button className="btn" onClick={undoLastRequest} disabled={chat.busy}
          title="Hoàn tác mọi thay đổi tệp của yêu cầu vừa rồi">↶ <span className="label-wide">Hoàn tác yêu cầu</span></button>
        <button className="btn" onClick={() => setDialog("settings")} title="Đổi mô hình AI">
          <span className={`dot ${chat.connected ? "" : "off"}`} aria-hidden /> {providerLabel}
          {settings?.pii_masking && <span className="pill ok" title="Đang che thông tin cá nhân trước khi gửi lên đám mây">PII</span>}
        </button>
        <button className="btn icon" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label={theme === "dark" ? "Chuyển giao diện sáng" : "Chuyển giao diện tối"} title="Đổi sáng/tối">
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </header>

      <div className="main">
        {!sessionId && (
          <section className="chat" aria-busy="true">
            <div className="chat-log"><p className="notice">Đang kết nối tới máy chủ…</p></div>
          </section>
        )}
        {sessionId && (
          <ChatPanel
            sessionId={sessionId}
            items={chat.items}
            busy={chat.busy}
            connected={chat.connected}
            activeFile={file?.name ?? null}
            selection={selection}
            prefill={prefill}
            onClearSelection={() => setSelection(null)}
            onSend={(text, images) => chat.send(text, images, selection, file?.name ?? null)}
            onCancel={chat.cancel}
            onOpenFile={setFileId}
            onError={setError}
          />
        )}

        <main
          className={`workspace ${dragging ? "dragging" : ""}`}
          onDragOver={(e) => { if (hasDraggedFiles(e)) { e.preventDefault(); setDragging(true); } }}
          onDragLeave={(e) => { if (e.currentTarget === e.target) setDragging(false); }}
          onDrop={(e) => { e.preventDefault(); setDragging(false); if (e.dataTransfer.files.length) upload(e.dataTransfer.files); }}
        >
          {files.length > 0 && <FileList files={files} selectedId={fileId} onSelect={setFileId} onUpload={upload} />}
          {file ? (
            <PreviewPane
              file={file}
              reloadKey={reloadKey}
              diff={diffs[file.id]}
              selection={selection}
              onSelect={setSelection}
              onUndo={() => versionAction(api.undo)}
              onRedo={() => versionAction(api.redo)}
              onHistory={() => setDialog("history")}
            />
          ) : (
            <Hero onPick={(text) => setPrefill({ text, nonce: Date.now() })} onUpload={upload} providerLabel={providerLabel} />
          )}
        </main>
      </div>

      {error && (
        <div className="toast" role="alert">
          <span>{error}</span>
          <button onClick={() => setError(null)} aria-label="Đóng thông báo">✕</button>
        </div>
      )}
      {chat.confirm && <ConfirmDialog req={chat.confirm} onAnswer={chat.answerConfirm} />}
      {dialog === "settings" && (
        <SettingsDialog onClose={() => setDialog(null)} onSaved={setSettings} onError={setError} />
      )}
      {dialog === "history" && file && (
        <HistoryDialog file={file} onClose={() => setDialog(null)} onError={setError}
          onRestored={() => { setDialog(null); afterVersionChange([file.id]); }} />
      )}
    </div>
  );
}

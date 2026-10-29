import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { ChatPanel } from "./components/ChatPanel";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { FileList } from "./components/FileList";
import { PreviewPane } from "./components/PreviewPane";
import type { ChatSession, FileDiff, OfficeFile, Selection } from "./types";
import { useChatSocket } from "./useChatSocket";

export default function App() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [files, setFiles] = useState<OfficeFile[]>([]);
  const [fileId, setFileId] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [diffs, setDiffs] = useState<Record<string, FileDiff>>({});
  const [error, setError] = useState<string | null>(null);

  const refreshFiles = useCallback(async (sid: string) => {
    const fs = await api.listFiles(sid);
    setFiles(fs);
    setFileId((cur) => (cur && fs.some((f) => f.id === cur) ? cur : fs[0]?.id ?? null));
  }, []);

  useEffect(() => {
    api.listSessions().then(async (ss) => {
      if (ss.length === 0) ss = [await api.createSession()];
      setSessions(ss);
      setSessionId(ss[0].id);
    }).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    setSelection(null);
    setDiffs({});
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

  const versionAction = async (fn: (id: string) => Promise<OfficeFile>) => {
    if (!fileId || !sessionId) return;
    try {
      await fn(fileId);
      setDiffs((d) => ({ ...d, [fileId]: {} }));
      setReloadKey((k) => k + 1);
      refreshFiles(sessionId);
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

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Trợ lý Office</h1>
        <select value={sessionId ?? ""} onChange={(e) => setSessionId(e.target.value)} aria-label="Phiên làm việc">
          {sessions.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
        </select>
        <button className="btn block" onClick={newSession}>+ Phiên mới</button>
        <FileList files={files} selectedId={fileId} onSelect={setFileId} onUpload={upload} />
      </aside>

      <main className="center">
        {file ? (
          <PreviewPane
            file={file}
            reloadKey={reloadKey}
            diff={diffs[file.id]}
            selection={selection}
            onSelect={setSelection}
            onUndo={() => versionAction(api.undo)}
            onRedo={() => versionAction(api.redo)}
          />
        ) : (
          <div className="empty">Chọn hoặc tải tệp lên để xem trước</div>
        )}
      </main>

      {sessionId && (
        <ChatPanel
          sessionId={sessionId}
          items={chat.items}
          busy={chat.busy}
          connected={chat.connected}
          selection={selection}
          onClearSelection={() => setSelection(null)}
          onSend={(text, images) => chat.send(text, images, selection)}
          onCancel={chat.cancel}
          onError={setError}
        />
      )}

      {error && (
        <div className="toast" role="alert">
          {error}
          <button onClick={() => setError(null)} aria-label="Đóng">✕</button>
        </div>
      )}
      {chat.confirm && <ConfirmDialog req={chat.confirm} onAnswer={chat.answerConfirm} />}
    </div>
  );
}

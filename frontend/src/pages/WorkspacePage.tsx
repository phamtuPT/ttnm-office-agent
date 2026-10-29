import { ArrowLeft, Check, Pencil, Undo2, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { ChatPanel } from "../components/ChatPanel";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { FileList } from "../components/FileList";
import { HistoryDialog } from "../components/HistoryDialog";
import { Thumb } from "../components/icons";
import { PreviewPane } from "../components/PreviewPane";
import { type BarProps, TopBar } from "../components/TopBar";
import { navigate } from "../router";
import type { ChatSession, FileDiff, OfficeFile, Selection } from "../types";
import { useChatSocket } from "../useChatSocket";

/** Không gian làm việc của một phiên: hội thoại với agent bên trái, tệp và xem trước bên phải. */
export function WorkspacePage({ sessionId, bar, onError }: { sessionId: string; bar: BarProps; onError: (m: string) => void }) {
  const [session, setSession] = useState<ChatSession | null>(null);
  const [files, setFiles] = useState<OfficeFile[]>([]);
  const [fileId, setFileId] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [diffs, setDiffs] = useState<Record<string, FileDiff>>({});
  const [showHistory, setShowHistory] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [editingTitle, setEditingTitle] = useState<string | null>(null);

  const refreshFiles = useCallback(async () => {
    const fs = await api.listFiles(sessionId);
    setFiles(fs);
    setFileId((cur) => (cur && fs.some((f) => f.id === cur) ? cur : fs[0]?.id ?? null));
  }, [sessionId]);

  useEffect(() => {
    setSelection(null);
    setDiffs({});
    setFileId(null);
    api.getSession(sessionId).then(setSession).catch(() => {
      onError("Không tìm thấy phiên làm việc này");
      navigate({ page: "home" });
    });
    refreshFiles().catch(() => {});
  }, [sessionId, refreshFiles]);

  const chat = useChatSocket(sessionId, {
    onFileChanged: (fid, diff) => {
      setDiffs((d) => ({ ...d, [fid]: diff }));
      setFileId(fid);
      setReloadKey((k) => k + 1);
      refreshFiles();
    },
    onTitle: (title) => setSession((s) => (s ? { ...s, title } : s)),
    onError,
  });

  const upload = async (list: FileList) => {
    for (const f of Array.from(list)) {
      try {
        const up = await api.uploadFile(sessionId, f);
        setFileId(up.id);
      } catch (e) {
        onError(`${f.name}: ${(e as Error).message}`);
      }
    }
    refreshFiles();
  };

  const afterVersionChange = (fids: string[]) => {
    setDiffs((d) => ({ ...d, ...Object.fromEntries(fids.map((id) => [id, {}])) }));
    setReloadKey((k) => k + 1);
    refreshFiles();
  };

  const versionAction = async (fn: (id: string) => Promise<OfficeFile>) => {
    if (!fileId) return;
    try {
      await fn(fileId);
      afterVersionChange([fileId]);
    } catch (e) {
      onError((e as Error).message);
    }
  };

  const undoLastRequest = async () => {
    try {
      const fs = await api.undoLastRequest(sessionId);
      afterVersionChange(fs.map((f) => f.id));
    } catch (e) {
      onError((e as Error).message);
    }
  };

  const saveTitle = async () => {
    const t = editingTitle?.trim();
    setEditingTitle(null);
    if (!t || !session || t === session.title) return;
    try {
      setSession(await api.renameSession(sessionId, t));
    } catch (e) {
      onError((e as Error).message);
    }
  };

  const file = files.find((f) => f.id === fileId);
  const hasDraggedFiles = (e: React.DragEvent) => Array.from(e.dataTransfer.types).includes("Files");

  return (
    <div className="app">
      <TopBar
        bar={bar}
        connected={chat.connected}
        left={
          <button className="btn icon" onClick={() => navigate({ page: "home" })} aria-label="Về trang chủ" title="Về trang chủ">
            <ArrowLeft size={17} aria-hidden />
          </button>
        }
        right={
          <>
            <div className="session-title">
              {editingTitle !== null ? (
                <form onSubmit={(e) => { e.preventDefault(); saveTitle(); }}>
                  <input autoFocus value={editingTitle} onChange={(e) => setEditingTitle(e.target.value)} onBlur={saveTitle}
                    onKeyDown={(e) => e.key === "Escape" && setEditingTitle(null)} aria-label="Tên phiên" maxLength={200} />
                  <button className="btn icon ghost" type="submit" aria-label="Lưu tên phiên"><Check size={16} aria-hidden /></button>
                </form>
              ) : (
                <button className="title-btn" onClick={() => setEditingTitle(session?.title ?? "")} title="Đổi tên phiên">
                  <span>{session?.title ?? "…"}</span>
                  <Pencil size={14} aria-hidden />
                </button>
              )}
            </div>
            <button className="btn" onClick={undoLastRequest} disabled={chat.busy} title="Hoàn tác mọi thay đổi tệp của yêu cầu vừa rồi">
              <Undo2 size={16} aria-hidden /> <span className="label-wide">Hoàn tác yêu cầu</span>
            </button>
          </>
        }
      />

      <div className="main">
        <ChatPanel
          sessionId={sessionId}
          items={chat.items}
          busy={chat.busy}
          connected={chat.connected}
          activeFile={file?.name ?? null}
          selection={selection}
          onClearSelection={() => setSelection(null)}
          onSend={(text, images) => chat.send(text, images, selection, file?.name ?? null)}
          onCancel={chat.cancel}
          onOpenFile={setFileId}
          onError={onError}
        />

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
              onHistory={() => setShowHistory(true)}
            />
          ) : (
            <div className="no-file">
              <Thumb kind={null} />
              <h2>Phiên này chưa có tệp</h2>
              <p className="muted">Kéo thả tệp .xlsx, .docx, .pptx vào đây, hoặc nhờ trợ lý tạo tệp mới bằng cách mô tả bạn cần gì.</p>
              <label className="btn solid">
                <Upload size={16} aria-hidden /> Tải tệp lên
                <input type="file" accept=".xlsx,.docx,.pptx" multiple hidden
                  onChange={(e) => { if (e.target.files) upload(e.target.files); e.target.value = ""; }} />
              </label>
            </div>
          )}
        </main>
      </div>

      {chat.confirm && <ConfirmDialog req={chat.confirm} onAnswer={chat.answerConfirm} />}
      {showHistory && file && (
        <HistoryDialog file={file} onClose={() => setShowHistory(false)} onError={onError}
          onRestored={() => { setShowHistory(false); afterVersionChange([file.id]); }} />
      )}
    </div>
  );
}

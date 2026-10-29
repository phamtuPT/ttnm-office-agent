import { FolderOpen, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "../api";
import { FileKindIcon, KIND_LABEL, KIND_NOUN, Thumb } from "../components/icons";
import { type BarProps, TopBar } from "../components/TopBar";
import { navigate } from "../router";
import type { ChatSession, FileKind } from "../types";

const START: { kind: FileKind; title: string; desc: string }[] = [
  { kind: "xlsx", title: "Bảng tính", desc: "Excel · công thức, biểu đồ, định dạng" },
  { kind: "docx", title: "Tài liệu", desc: "Word · báo cáo, hợp đồng, công văn" },
  { kind: "pptx", title: "Bản trình chiếu", desc: "PowerPoint · slide 16:9, ghi chú" },
];

type Filter = "all" | FileKind;
type Sort = "recent" | "name";

/** Ảnh thu nhỏ nội dung thật của tệp chính trong phiên; lỗi hoặc chưa có tệp thì dùng ảnh minh hoạ. */
function SessionPreview({ session }: { session: ChatSession }) {
  const [failed, setFailed] = useState(false);
  const p = session.preview;
  if (!p || failed) return <Thumb kind={session.kind} />;
  return <img src={api.thumbnailUrl(p.file_id, p.version)} alt="" loading="lazy" onError={() => setFailed(true)} />;
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  if (d.toDateString() === today.toDateString())
    return `hôm nay, ${d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}`;
  return d.toLocaleDateString("vi-VN", { day: "numeric", month: "short", year: "numeric" });
}

/** Trang chủ: chọn loại tệp để bắt đầu phiên mới, bên dưới là các phiên làm việc trước đó. */
export function HomePage({ bar, onError }: { bar: BarProps; onError: (m: string) => void }) {
  const [sessions, setSessions] = useState<ChatSession[] | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("recent");
  const [busy, setBusy] = useState(false);
  const [toDelete, setToDelete] = useState<ChatSession | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);

  const load = () => api.listSessions().then(setSessions).catch((e) => onError(`Không kết nối được máy chủ: ${e.message}`));
  useEffect(() => { load(); }, []);

  const start = async (kind?: FileKind, files?: FileList) => {
    setBusy(true);
    try {
      const s = await api.createSession(kind);
      for (const f of Array.from(files ?? [])) {
        try {
          await api.uploadFile(s.id, f);
        } catch (e) {
          onError(`${f.name}: ${(e as Error).message}`);
        }
      }
      navigate({ page: "session", id: s.id });
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (s: ChatSession) => {
    setToDelete(null);
    try {
      await api.deleteSession(s.id);
      setSessions((xs) => xs?.filter((x) => x.id !== s.id) ?? null);
    } catch (e) {
      onError((e as Error).message);
    }
  };

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const xs = (sessions ?? []).filter((s) =>
      (filter === "all" || s.files.some((f) => f.kind === filter)) &&
      (!q || s.title.toLowerCase().includes(q) || s.files.some((f) => f.name.toLowerCase().includes(q))));
    return sort === "name" ? [...xs].sort((a, b) => a.title.localeCompare(b.title, "vi")) : xs;
  }, [sessions, query, filter, sort]);

  return (
    <div className="app home">
      <TopBar bar={bar} right={
        <label className="search">
          <Search size={16} aria-hidden />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm phiên hoặc tệp…" aria-label="Tìm phiên hoặc tệp" />
        </label>
      } />

      <main className="home-main">
        <section className="start" aria-labelledby="start-title">
          <div className="home-inner">
            <h1 id="start-title" className="section-heading">Bắt đầu làm việc mới</h1>
            <div className="start-grid">
              {START.map((t) => (
                <button key={t.kind} className={`start-tile ${t.kind}`} onClick={() => start(t.kind)} disabled={busy}>
                  <span className="tile-thumb"><Thumb kind={t.kind} /></span>
                  <span className="tile-body">
                    <FileKindIcon kind={t.kind} size={20} />
                    <span><b>{t.title}</b><small>{t.desc}</small></span>
                  </span>
                </button>
              ))}
              <button className="start-tile open" onClick={() => uploadRef.current?.click()} disabled={busy}>
                <span className="tile-thumb"><Thumb kind={null} /></span>
                <span className="tile-body">
                  <FolderOpen size={20} className="kind-icon none" aria-hidden />
                  <span><b>Mở tệp có sẵn</b><small>Tải lên .xlsx, .docx, .pptx</small></span>
                </span>
              </button>
              <input ref={uploadRef} type="file" accept=".xlsx,.docx,.pptx" multiple hidden
                onChange={(e) => { if (e.target.files?.length) start(undefined, e.target.files); e.target.value = ""; }} />
            </div>
          </div>
        </section>

        <section className="recent" aria-labelledby="recent-title">
          <div className="home-inner">
            <div className="recent-head">
              <h2 id="recent-title" className="section-heading">Phiên làm việc gần đây</h2>
              {sessions && <span className="count">{sessions.length}</span>}
              <span className="spacer" />
              <div className="segmented" role="group" aria-label="Lọc theo loại tệp">
                {(["all", "xlsx", "docx", "pptx"] as Filter[]).map((k) => (
                  <button key={k} className={filter === k ? "active" : ""} onClick={() => setFilter(k)} aria-pressed={filter === k}>
                    {k !== "all" && <FileKindIcon kind={k} size={14} />}{k === "all" ? "Tất cả" : KIND_LABEL[k]}
                  </button>
                ))}
              </div>
              <select className="select" value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sắp xếp">
                <option value="recent">Mở gần đây</option>
                <option value="name">Tên A → Z</option>
              </select>
            </div>

            {sessions === null && <p className="hint">Đang tải…</p>}
            {sessions && shown.length === 0 && (
              <div className="empty-recent">
                {sessions.length === 0 ? "Chưa có phiên làm việc nào. Chọn một loại tệp ở trên để bắt đầu." : "Không có phiên nào khớp bộ lọc."}
              </div>
            )}
            <div className="session-grid">
              {shown.map((s) => (
                <article key={s.id} className="session-card">
                  <button className="session-open" onClick={() => navigate({ page: "session", id: s.id })}>
                    <span className={`session-thumb ${s.kind ?? "none"}`}><SessionPreview session={s} /></span>
                    <span className="session-info">
                      <b title={s.title}>{s.title}</b>
                      <span className="session-meta">
                        <FileKindIcon kind={s.kind} size={15} />
                        {s.kind ? KIND_NOUN[s.kind] : "Chưa có tệp"} · {formatWhen(s.updated_at)}
                      </span>
                      <span className="session-files">
                        {s.files.length} tệp · {s.message_count} yêu cầu
                      </span>
                    </span>
                  </button>
                  <button className="btn icon ghost session-delete" onClick={() => setToDelete(s)} aria-label={`Xoá phiên ${s.title}`} title="Xoá phiên">
                    <Trash2 size={16} aria-hidden />
                  </button>
                </article>
              ))}
            </div>
          </div>
        </section>
      </main>

      {toDelete && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="del-title">
          <div className="modal">
            <h3 id="del-title">Xoá phiên “{toDelete.title}”?</h3>
            <p className="muted">Toàn bộ {toDelete.files.length} tệp, các phiên bản sao lưu và lịch sử hội thoại của phiên này sẽ bị xoá vĩnh viễn. Hãy tải về những tệp cần giữ trước.</p>
            <div className="modal-actions">
              <button className="btn" onClick={() => setToDelete(null)} autoFocus>Huỷ</button>
              <button className="btn danger" onClick={() => remove(toDelete)}><Trash2 size={15} aria-hidden /> Xoá vĩnh viễn</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

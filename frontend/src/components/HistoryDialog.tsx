import { useEffect, useState } from "react";
import { api } from "../api";
import type { FileDiff, FileVersion, OfficeFile } from "../types";
import { MathText } from "./MathText";

/** Lịch sử phiên bản theo từng yêu cầu: xem đã đổi gì và khôi phục một nhấp (khôi phục cũng hoàn tác được). */
export function HistoryDialog(p: { file: OfficeFile; onClose: () => void; onRestored: () => void; onError: (m: string) => void }) {
  const [versions, setVersions] = useState<FileVersion[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);

  useEffect(() => {
    api.versions(p.file.id).then(setVersions).catch((e) => p.onError(e.message));
  }, [p.file.id, p.file.current_version]);

  const restore = async (n: number) => {
    try {
      await api.restore(p.file.id, n);
      p.onRestored();
    } catch (e) {
      p.onError((e as Error).message);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="hist-title" onClick={p.onClose}>
      <div className="modal wide" onClick={(e) => e.stopPropagation()}>
        <h3 id="hist-title">Lịch sử — {p.file.name}</h3>
        <p className="hint">Mỗi dòng là một yêu cầu. Khôi phục tạo phiên bản mới, nên vẫn hoàn tác được lần khôi phục.</p>
        {!versions && <p className="hint">Đang tải…</p>}
        <ol className="history">
          {versions?.map((v) => (
            <li key={v.number} className={v.current ? "current" : ""}>
              <div className="row">
                <span className="vnum">v{v.number}</span>
                <span className="when">{new Date(v.created_at).toLocaleString("vi-VN")}</span>
                <span className="what">{v.request ? `“${v.request}”` : v.summary}</span>
                {v.current ? <span className="pill ok">Đang dùng</span> : (
                  <button className="btn small" onClick={() => restore(v.number)}>Khôi phục</button>
                )}
              </div>
              <button className="link" onClick={() => setOpen(open === v.number ? null : v.number)} aria-expanded={open === v.number}>
                {v.summary}
              </button>
              {open === v.number && <DiffView diff={v.diff} />}
            </li>
          ))}
        </ol>
        <div className="modal-actions">
          <button className="btn" onClick={p.onClose} autoFocus>Đóng</button>
        </div>
      </div>
    </div>
  );
}

function DiffView({ diff }: { diff: FileDiff }) {
  if (diff.created) return <p className="hint">Tệp được tạo ở phiên bản này.</p>;
  return (
    <div className="diff">
      {diff.cells?.map((c, i) => (
        <div key={i}>
          {c.sheet}!{c.ref}: {c.kind === "format" ? "đổi định dạng" : <><del>{fmt(c.before)}</del> → <ins>{fmt(c.after)}</ins></>}
        </div>
      ))}
      {diff.charts?.map((c, i) => <div key={i}>Biểu đồ ở {c.sheet}: {c.before} → {c.after}</div>)}
      {diff.paragraphs?.map((d, i) => (
        <div key={i}>
          {d.before.map((t, j) => <del key={`b${j}`}>{t ? <MathText text={t} /> : "(đoạn trống)"}</del>)}
          {d.after.map((t, j) => <ins key={`a${j}`}>{t ? <MathText text={t} /> : "(đoạn trống)"}</ins>)}
        </div>
      ))}
      {diff.slides?.map((s, i) => (
        <div key={i}>Slide {s.index + 1}: {s.before === null ? "thêm mới" : s.after === null ? "đã xoá" : "nội dung thay đổi"}</div>
      ))}
      {diff.styles && <div>Đổi kiểu chữ (Heading, Normal…) hoặc lề trang của tài liệu</div>}
      {diff.design && <div>Đổi thiết kế / bảng màu của bài trình chiếu</div>}
    </div>
  );
}

const fmt = (v: unknown) => (v === null || v === undefined || v === "" ? "(trống)" : String(v));

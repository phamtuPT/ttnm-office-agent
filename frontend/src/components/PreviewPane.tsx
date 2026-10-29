import { useEffect, useRef, useState } from "react";
import * as XLSX from "xlsx";
import { renderAsync } from "docx-preview";
import { api } from "../api";
import type { FileDiff, OfficeFile, Selection } from "../types";

interface Props {
  file: OfficeFile;
  reloadKey: number;
  diff: FileDiff | undefined;
  selection: Selection | null;
  onSelect: (s: Selection | null) => void;
  onUndo: () => void;
  onRedo: () => void;
}

export function PreviewPane(p: Props) {
  const { file } = p;
  const [printView, setPrintView] = useState(false);
  const sel = p.selection?.file === file.name ? p.selection : null;

  return (
    <section className="preview">
      <header className="preview-head">
        <b className="name">{file.name}</b>
        <span className="ver">Phiên bản {file.current_version}/{file.latest_version}</span>
        <button className="btn" onClick={p.onUndo} disabled={file.current_version <= 1} title="Hoàn tác thay đổi gần nhất">↶ Hoàn tác</button>
        <button className="btn" onClick={p.onRedo} disabled={file.current_version >= file.latest_version} title="Làm lại">↷ Làm lại</button>
        {file.kind === "docx" && (
          <button className="btn" onClick={() => setPrintView((v) => !v)}>{printView ? "Dàn ý" : "Bản in"}</button>
        )}
        <a className="btn" href={api.fileContentUrl(file.id)} download={file.name}>Tải về</a>
      </header>
      <p className="hint">
        {file.kind === "xlsx" && "Kéo chuột để chọn vùng ô cho trợ lý sửa."}
        {file.kind === "docx" && !printView && "Bấm vào đoạn để chọn (Ctrl+bấm để chọn nhiều)."}
        {file.kind === "pptx" && "Bấm vào slide để chọn (Ctrl+bấm để chọn nhiều)."}
      </p>
      <div className="preview-body">
        {file.kind === "xlsx" && <XlsxView {...p} selection={sel} />}
        {file.kind === "docx" && (printView ? <DocxPrint {...p} /> : <OutlineView {...p} selection={sel} />)}
        {file.kind === "pptx" && <OutlineView {...p} selection={sel} />}
      </div>
    </section>
  );
}

// ---------- Excel ----------

const MAX_ROWS = 300;
const MAX_COLS = 40;

function XlsxView({ file, reloadKey, diff, selection, onSelect }: Props) {
  const [wb, setWb] = useState<XLSX.WorkBook | null>(null);
  const [sheet, setSheet] = useState<string>("");
  const [drag, setDrag] = useState<{ a: XLSX.CellAddress; b: XLSX.CellAddress } | null>(null);

  useEffect(() => {
    fetch(api.fileContentUrl(file.id))
      .then((r) => r.arrayBuffer())
      .then((buf) => {
        const book = XLSX.read(buf, { cellFormula: true });
        setWb(book);
        setSheet((s) => (book.SheetNames.includes(s) ? s : book.SheetNames[0]));
      });
  }, [file.id, reloadKey]);

  if (!wb) return <p className="hint">Đang tải…</p>;
  const ws = wb.Sheets[sheet];
  const range = XLSX.utils.decode_range(ws?.["!ref"] ?? "A1");
  const rows = Math.min(range.e.r, MAX_ROWS - 1);
  const cols = Math.min(Math.max(range.e.c, 5), MAX_COLS - 1);
  const changed = new Set((diff?.cells ?? []).filter((c) => c.sheet === sheet).map((c) => c.ref));

  const selRange = drag
    ? { s: { r: Math.min(drag.a.r, drag.b.r), c: Math.min(drag.a.c, drag.b.c) }, e: { r: Math.max(drag.a.r, drag.b.r), c: Math.max(drag.a.c, drag.b.c) } }
    : selection?.sheet === sheet && selection.range ? XLSX.utils.decode_range(selection.range) : null;
  const inSel = (r: number, c: number) => !!selRange && r >= selRange.s.r && r <= selRange.e.r && c >= selRange.s.c && c <= selRange.e.c;

  const finish = () => {
    if (!drag || !selRange) return;
    onSelect({ file: file.name, sheet, range: XLSX.utils.encode_range(selRange) });
    setDrag(null);
  };

  const show = (addr: string) => {
    const c = ws?.[addr] as XLSX.CellObject | undefined;
    if (!c) return "";
    // openpyxl không lưu giá trị đã tính của công thức → hiển thị công thức
    return c.w ?? (c.v !== undefined ? String(c.v) : c.f ? `=${c.f}` : "");
  };

  return (
    <div className="sheet-wrap" onMouseUp={finish} onMouseLeave={finish}>
      <div className="tabs">
        {wb.SheetNames.map((n) => (
          <button key={n} className={n === sheet ? "active" : ""} onClick={() => setSheet(n)}>{n}</button>
        ))}
      </div>
      <div className="grid-scroll">
        <table className="grid">
          <thead>
            <tr>
              <th />
              {Array.from({ length: cols + 1 }, (_, c) => <th key={c}>{XLSX.utils.encode_col(c)}</th>)}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: rows + 1 }, (_, r) => (
              <tr key={r}>
                <th>{r + 1}</th>
                {Array.from({ length: cols + 1 }, (_, c) => {
                  const addr = XLSX.utils.encode_cell({ r, c });
                  return (
                    <td
                      key={c}
                      className={`${inSel(r, c) ? "sel" : ""} ${changed.has(addr) ? "changed" : ""}`}
                      onMouseDown={(e) => { e.preventDefault(); setDrag({ a: { r, c }, b: { r, c } }); }}
                      onMouseEnter={() => drag && setDrag({ ...drag, b: { r, c } })}
                    >
                      {show(addr)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {range.e.r >= MAX_ROWS && <p className="hint">Chỉ hiển thị {MAX_ROWS} dòng đầu.</p>}
    </div>
  );
}

// ---------- Word (bản in) ----------

function DocxPrint({ file, reloadKey }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    fetch(api.fileContentUrl(file.id))
      .then((r) => r.blob())
      .then((b) => ref.current && renderAsync(b, ref.current, undefined, { inWrapper: true }));
  }, [file.id, reloadKey]);
  return <div ref={ref} className="docx-print" />;
}

// ---------- Word / PowerPoint (dàn ý, chọn đoạn/slide) ----------

function OutlineView({ file, reloadKey, diff, selection, onSelect }: Props) {
  const [outline, setOutline] = useState<any>(null);
  useEffect(() => {
    api.outline(file.id).then(setOutline);
  }, [file.id, reloadKey]);
  if (!outline) return <p className="hint">Đang tải…</p>;

  const key = file.kind === "docx" ? "paragraphs" : "slides";
  const chosen: number[] = selection?.[key] ?? [];
  const changed = new Set<number>(
    file.kind === "docx"
      ? (diff?.paragraphs ?? []).flatMap((d) => d.after.map((_, i) => d.after_index + i))
      : (diff?.slides ?? []).map((d) => d.index),
  );

  const toggle = (i: number, multi: boolean) => {
    const next = multi ? (chosen.includes(i) ? chosen.filter((x) => x !== i) : [...chosen, i].sort((a, b) => a - b))
      : chosen.length === 1 && chosen[0] === i ? [] : [i];
    onSelect(next.length ? { file: file.name, [key]: next } : null);
  };

  const items: { index: number; label: string; body: string }[] =
    file.kind === "docx"
      ? outline.paragraphs.map((p: any) => ({ index: p.index, label: p.style, body: p.text || "(đoạn trống)" }))
      : outline.slides.map((s: any) => ({
          index: s.index,
          label: `Slide ${s.index + 1} · ${s.layout}`,
          body: s.shapes.map((sh: any) => sh.text).filter(Boolean).join("\n") || "(không có chữ)",
        }));

  return (
    <ol className={`outline ${file.kind}`}>
      {items.map((it) => (
        <li
          key={it.index}
          className={`${chosen.includes(it.index) ? "sel" : ""} ${changed.has(it.index) ? "changed" : ""}`}
          onClick={(e) => toggle(it.index, e.ctrlKey || e.metaKey)}
        >
          <small>{it.label}</small>
          <div>{it.body}</div>
        </li>
      ))}
    </ol>
  );
}

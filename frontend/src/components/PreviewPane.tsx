import { Download, History, ListTree, Printer, Redo2, Undo2 } from "lucide-react";
import { SquareFunction } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import * as XLSX from "xlsx";
import { renderAsync } from "docx-preview";
import { api } from "../api";
import type { FileDiff, OfficeFile, Selection } from "../types";
import { type ChartInfo, ChartView } from "./ChartView";
import { FileKindIcon } from "./icons";
import { MathText, replaceDocxMath } from "./MathText";
import { createEvaluator, formatValue } from "../formulas";

interface Props {
  file: OfficeFile;
  reloadKey: number;
  diff: FileDiff | undefined;
  selection: Selection | null;
  onSelect: (s: Selection | null) => void;
  onUndo: () => void;
  onRedo: () => void;
  onHistory: () => void;
}

export function PreviewPane(p: Props) {
  const { file } = p;
  const [printView, setPrintView] = useState(false);
  const sel = p.selection?.file === file.name ? p.selection : null;

  return (
    <section className="preview">
      <header className="preview-head">
        <FileKindIcon kind={file.kind} size={24} />
        <b className="name">{file.name}</b>
        <span className="pill mono">v{file.current_version}</span>
        <span className="spacer" />
        <button className="btn" onClick={p.onUndo} disabled={file.current_version <= file.oldest_version} title="Hoàn tác yêu cầu gần nhất trên tệp này"><Undo2 size={16} aria-hidden /> Hoàn tác</button>
        <button className="btn" onClick={p.onRedo} disabled={file.current_version >= file.latest_version} title="Làm lại"><Redo2 size={16} aria-hidden /> Làm lại</button>
        <button className="btn" onClick={p.onHistory} title="Xem thay đổi theo từng yêu cầu, khôi phục phiên bản cũ"><History size={16} aria-hidden /> Lịch sử</button>
        {file.kind === "docx" && (
          <button className="btn" onClick={() => setPrintView((v) => !v)} aria-pressed={printView}>{printView ? <><ListTree size={16} aria-hidden /> Dàn ý</> : <><Printer size={16} aria-hidden /> Bản in</>}</button>
        )}
        <a className="btn primary" href={api.fileContentUrl(file.id)} download={file.name}><Download size={16} aria-hidden /> Tải về</a>
      </header>
      <p className="hint">
        {file.kind === "xlsx" && "Bấm một ô để đặt vị trí bắt đầu. Kéo chọn nhiều ô để giới hạn vùng trợ lý được sửa."}
        {file.kind === "docx" && !printView && "Bấm vào đoạn để chọn (Ctrl+bấm để chọn nhiều)."}
        {file.kind === "pptx" && "Bấm vào slide để chọn (Ctrl+bấm để chọn nhiều)."}
      </p>
      <div className="preview-body">
        {file.kind === "xlsx" && <XlsxView {...p} selection={sel} />}
        {file.kind === "docx" && (printView ? <DocxPrint {...p} /> : <OutlineView {...p} selection={sel} />)}
        {file.kind === "pptx" && <SlidesView {...p} selection={sel} />}
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
  const [charts, setCharts] = useState<Record<string, ChartInfo[]>>({});
  const [active, setActive] = useState<XLSX.CellAddress | null>(null);
  const evaluator = useMemo(() => (wb ? createEvaluator(wb) : null), [wb]);

  useEffect(() => {
    api.outline(file.id)
      .then((o) => setCharts(Object.fromEntries(o.sheets.map((s: any) => [s.name, s.charts ?? []]))))
      .catch(() => setCharts({}));
    fetch(api.fileContentUrl(file.id))
      .then((r) => r.arrayBuffer())
      .then((buf) => {
        const book = XLSX.read(buf, { cellFormula: true, sheetStubs: true, cellNF: true });
        setWb(book);
        setSheet((s) => (book.SheetNames.includes(s) ? s : book.SheetNames[0]));
      });
  }, [file.id, reloadKey]);

  if (!wb || !evaluator) return <p className="hint">Đang tải…</p>;
  const ws = wb.Sheets[sheet];
  const range = XLSX.utils.decode_range(ws?.["!ref"] ?? "A1");
  // Luôn hiện tối thiểu một lưới 30×8 để bảng tính trống vẫn trông như bảng tính
  const rows = Math.min(Math.max(range.e.r, 29), MAX_ROWS - 1);
  const cols = Math.min(Math.max(range.e.c, 7), MAX_COLS - 1);
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

  /** Nội dung hiển thị của ô: ô công thức hiện KẾT QUẢ (như Excel); công thức nằm ở thanh công thức. */
  const show = (r: number, c: number): { text: string; cls: string } => {
    const cell = ws?.[XLSX.utils.encode_cell({ r, c })] as XLSX.CellObject | undefined;
    if (!cell) return { text: "", cls: "" };
    if (cell.f) {
      const res = evaluator.cell(sheet, r, c, cell.f);
      if (res.unsupported) return { text: `=${cell.f}`, cls: "formula" }; // hàm chưa tính được → hiện công thức
      if (res.error) return { text: res.error, cls: "error" };
      return { text: formatValue(res.value, cell.z), cls: typeof res.value === "number" ? "num" : "" };
    }
    if (cell.t === "z") return { text: "", cls: "" };
    return { text: cell.w ?? (cell.v !== undefined ? String(cell.v) : ""), cls: cell.t === "n" ? "num" : "" };
  };

  // Thanh công thức: địa chỉ ô đang chọn + công thức (hoặc giá trị gốc) của ô đó
  const activeAddr = active ? XLSX.utils.encode_cell(active) : "";
  const activeCell = active ? (ws?.[activeAddr] as XLSX.CellObject | undefined) : undefined;
  const activeContent = activeCell?.f ? `=${activeCell.f.replace(/_xlfn\./gi, "")}` : activeCell && activeCell.t !== "z" ? String(activeCell.v ?? "") : "";

  return (
    <div className="sheet-wrap" onMouseUp={finish} onMouseLeave={finish}>
      <div className="tabs">
        {wb.SheetNames.map((n) => (
          <button key={n} className={n === sheet ? "active" : ""} onClick={() => { setSheet(n); setActive(null); }}>{n}</button>
        ))}
      </div>
      <div className="formula-bar" aria-label="Thanh công thức">
        <span className="name-box" aria-label="Ô đang chọn">{activeAddr}</span>
        <SquareFunction size={16} className="fx" aria-hidden />
        <span className="formula-text" title={activeContent}>{activeContent}</span>
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
                  const { text, cls } = show(r, c);
                  const isActive = active?.r === r && active?.c === c;
                  return (
                    <td
                      key={c}
                      className={`${inSel(r, c) ? "sel" : ""} ${changed.has(addr) ? "changed" : ""} ${cls} ${isActive ? "active" : ""}`}
                      onMouseDown={(e) => { e.preventDefault(); setActive({ r, c }); setDrag({ a: { r, c }, b: { r, c } }); }}
                      onMouseEnter={() => drag && setDrag({ ...drag, b: { r, c } })}
                    >
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {range.e.r >= MAX_ROWS && <p className="hint">Chỉ hiển thị {MAX_ROWS} dòng đầu.</p>}
      {(charts[sheet]?.length ?? 0) > 0 && (
        <div className="charts" aria-label="Biểu đồ trong sheet">
          {charts[sheet].map((ch, i) => <ChartView key={i} chart={ch} wb={wb} sheet={sheet} evaluate={evaluator.cell} />)}
        </div>
      )}
    </div>
  );
}

// ---------- Word (bản in) ----------

function DocxPrint({ file, reloadKey }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    fetch(api.fileContentUrl(file.id))
      .then((r) => r.blob())
      .then((b) => ref.current && renderAsync(b, ref.current, undefined, { inWrapper: true }))
      .then(() => api.equations(file.id))
      .then((eqs) => ref.current && eqs.length && replaceDocxMath(ref.current, eqs))
      .catch(() => undefined); // công thức vẽ lại thất bại: vẫn còn bản của docx-preview
  }, [file.id, reloadKey]);
  return <div ref={ref} className="docx-print" />;
}

// ---------- PowerPoint: ảnh slide (LibreOffice) hoặc dàn ý ----------

function SlidesView(p: Props) {
  const { file, reloadKey, diff, selection, onSelect } = p;
  const [pages, setPages] = useState<{ available: boolean; pages: number; version?: number } | null>(null);
  useEffect(() => {
    setPages(null);
    api.pages(file.id).then(setPages).catch(() => setPages({ available: false, pages: 0 }));
  }, [file.id, reloadKey]);
  if (!pages) return <p className="hint">Đang dựng ảnh slide…</p>;
  if (!pages.available) return <OutlineView {...p} />;

  const chosen = selection?.slides ?? [];
  const changed = new Set((diff?.slides ?? []).map((d) => d.index));
  const toggle = (i: number, multi: boolean) => {
    const next = multi ? (chosen.includes(i) ? chosen.filter((x) => x !== i) : [...chosen, i].sort((a, b) => a - b))
      : chosen.length === 1 && chosen[0] === i ? [] : [i];
    onSelect(next.length ? { file: file.name, slides: next } : null);
  };
  return (
    <ol className="slides">
      {Array.from({ length: pages.pages }, (_, i) => (
        <li key={i} className={`${chosen.includes(i) ? "sel" : ""} ${changed.has(i) ? "changed" : ""}`}
          onClick={(e) => toggle(i, e.ctrlKey || e.metaKey)}>
          <img src={api.pageUrl(file.id, i, pages.version ?? 0)} alt={`Slide ${i + 1}`} loading="lazy" />
          <small>Slide {i + 1}</small>
        </li>
      ))}
    </ol>
  );
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
          <div><MathText text={it.body} /></div>
        </li>
      ))}
    </ol>
  );
}

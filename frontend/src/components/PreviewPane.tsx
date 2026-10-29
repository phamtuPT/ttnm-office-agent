import { Download, History, ListTree, Printer, Redo2, Undo2 } from "lucide-react";
import { SquareFunction } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
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
  /** Người dùng vừa sửa ô trực tiếp trên lưới (đã lưu thành phiên bản mới). */
  onEdited?: (diff: FileDiff) => void;
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
        {file.kind === "xlsx" && "Bấm một ô để đặt vị trí bắt đầu, kéo (hoặc Shift + mũi tên) để giới hạn vùng trợ lý được sửa. Gõ hoặc nhấp đúp để sửa ô."}
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

function XlsxView({ file, reloadKey, diff, selection, onSelect, onEdited }: Props) {
  const [wb, setWb] = useState<XLSX.WorkBook | null>(null);
  const [sheet, setSheet] = useState<string>("");
  const [drag, setDrag] = useState<{ a: XLSX.CellAddress; b: XLSX.CellAddress } | null>(null);
  const [charts, setCharts] = useState<Record<string, ChartInfo[]>>({});
  const [active, setActive] = useState<XLSX.CellAddress | null>(null);
  const [anchor, setAnchor] = useState<XLSX.CellAddress | null>(null); // đầu vùng chọn khi giữ Shift
  const [edit, setEdit] = useState<string | null>(null); // nội dung đang gõ vào ô đang chọn
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const gridRef = useRef<HTMLTableElement>(null);
  const editDone = useRef(false); // Enter/Esc đã xử lý → bỏ qua blur theo sau
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
    setAnchor(drag.a);
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

  /** Nội dung gốc của ô (công thức "=..." hoặc giá trị) — hiện ở thanh công thức và khi bắt đầu sửa. */
  const source = (addr: XLSX.CellAddress | null) => {
    const cell = addr ? (ws?.[XLSX.utils.encode_cell(addr)] as XLSX.CellObject | undefined) : undefined;
    if (cell?.f) return `=${cell.f.replace(/_xlfn\./gi, "")}`;
    return cell && cell.t !== "z" ? String(cell.v ?? "") : "";
  };
  const activeAddr = active ? XLSX.utils.encode_cell(active) : "";
  const activeContent = source(active);
  const cellId = (addr: string) => `xl-${addr}`;

  const move = (r: number, c: number, extend = false) => {
    const next = { r: Math.max(0, Math.min(r, rows)), c: Math.max(0, Math.min(c, cols)) };
    const start = extend ? (anchor ?? active ?? next) : next;
    setActive(next);
    if (!extend) setAnchor(next);
    const rng = { s: { r: Math.min(start.r, next.r), c: Math.min(start.c, next.c) }, e: { r: Math.max(start.r, next.r), c: Math.max(start.c, next.c) } };
    onSelect({ file: file.name, sheet, range: XLSX.utils.encode_range(rng) });
    requestAnimationFrame(() => document.getElementById(cellId(XLSX.utils.encode_cell(next)))?.scrollIntoView({ block: "nearest", inline: "nearest" }));
  };

  const save = async (cells: { ref: string; value: string | null }[]) => {
    setSaving(true);
    setEditError(null);
    try {
      const res = await api.editCells(file.id, sheet, cells);
      onEdited?.(res.diff);
    } catch (e) {
      setEditError((e as Error).message);
    } finally {
      setSaving(false);
      gridRef.current?.focus();
    }
  };

  const startEdit = (value: string) => {
    editDone.current = false;
    setEdit(value);
  };

  /** Kết thúc sửa: lưu nếu khác nội dung cũ rồi đi tiếp (Enter xuống, Tab sang phải) như Excel. */
  const commit = (value: string, step?: [number, number]) => {
    if (!active) return;
    editDone.current = true;
    setEdit(null);
    if (value !== activeContent) save([{ ref: activeAddr, value }]);
    else gridRef.current?.focus();
    if (step) move(active.r + step[0], active.c + step[1]);
  };

  const clearSelection = () => {
    const rng = selRange ?? (active ? { s: active, e: active } : null);
    if (!rng) return;
    const cells: { ref: string; value: null }[] = [];
    for (let r = rng.s.r; r <= rng.e.r; r++) {
      for (let c = rng.s.c; c <= rng.e.c; c++) {
        const ref = XLSX.utils.encode_cell({ r, c });
        const cell = ws?.[ref] as XLSX.CellObject | undefined;
        if (cell && cell.t !== "z") cells.push({ ref, value: null });
      }
    }
    if (cells.length) save(cells.slice(0, 500));
  };

  const onGridKey = (e: React.KeyboardEvent) => {
    if (edit !== null) return;
    if (!active) {
      if (e.key.startsWith("Arrow")) { e.preventDefault(); move(0, 0); }
      return;
    }
    const arrows: Record<string, [number, number]> = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
    if (e.key in arrows) {
      e.preventDefault();
      const [dr, dc] = arrows[e.key];
      // Shift: mở rộng vùng chọn từ ô neo, ô "đầu" là ô đang di chuyển
      move(active.r + dr, active.c + dc, e.shiftKey);
    } else if (e.key === "Enter") {
      e.preventDefault();
      move(active.r + (e.shiftKey ? -1 : 1), active.c);
    } else if (e.key === "F2") {
      e.preventDefault();
      startEdit(activeContent);
    } else if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      clearSelection();
    } else if (e.key === "Escape") {
      onSelect(null);
    } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      flushSync(() => startEdit(e.key)); // gõ thẳng như Excel: ký tự đầu thay nội dung ô (cả chữ có dấu từ Unikey)
    } else if (e.key === "Process") {
      // Bộ gõ kiểu IME (Telex của Windows): chưa biết ký tự → mở ô nhập ngay, không chặn phím để IME soạn chữ vào đó
      flushSync(() => startEdit(""));
    }
  };

  const onEditKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commit(e.currentTarget.value, [e.shiftKey ? -1 : 1, 0]);
    } else if (e.key === "Tab") {
      e.preventDefault();
      commit(e.currentTarget.value, [0, e.shiftKey ? -1 : 1]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      editDone.current = true;
      setEdit(null);
      gridRef.current?.focus();
    }
  };

  return (
    <div className="sheet-wrap" onMouseUp={finish} onMouseLeave={finish}>
      <div className="tabs">
        {wb.SheetNames.map((n) => (
          <button key={n} className={n === sheet ? "active" : ""} onClick={() => { setSheet(n); setActive(null); setEdit(null); }}>{n}</button>
        ))}
      </div>
      <div className="formula-bar" aria-label="Thanh công thức">
        <span className="name-box" aria-label="Ô đang chọn">{activeAddr}</span>
        <SquareFunction size={16} className="fx" aria-hidden />
        <span className="formula-text" title={edit ?? activeContent}>{edit ?? activeContent}</span>
        {saving && <span className="formula-status">Đang lưu…</span>}
        {editError && <span className="formula-status error" role="alert">{editError}</span>}
      </div>
      <div className="grid-scroll">
        <table
          ref={gridRef}
          className="grid"
          role="grid"
          aria-label={`Trang tính ${sheet}. Phím mũi tên để di chuyển, gõ để sửa ô, Enter để lưu`}
          aria-multiselectable="true"
          aria-activedescendant={active ? cellId(activeAddr) : undefined}
          tabIndex={0}
          onKeyDown={onGridKey}
        >
          <thead>
            <tr>
              <th />
              {Array.from({ length: cols + 1 }, (_, c) => <th key={c} scope="col">{XLSX.utils.encode_col(c)}</th>)}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: rows + 1 }, (_, r) => (
              <tr key={r}>
                <th scope="row">{r + 1}</th>
                {Array.from({ length: cols + 1 }, (_, c) => {
                  const addr = XLSX.utils.encode_cell({ r, c });
                  const { text, cls } = show(r, c);
                  const isActive = active?.r === r && active?.c === c;
                  return (
                    <td
                      key={c}
                      id={cellId(addr)}
                      role="gridcell"
                      aria-selected={inSel(r, c) || isActive}
                      className={`${inSel(r, c) ? "sel" : ""} ${changed.has(addr) ? "changed" : ""} ${cls} ${isActive ? "active" : ""} ${isActive && edit !== null ? "editing" : ""}`}
                      onMouseDown={(e) => {
                        if (edit !== null && isActive) return; // bấm trong ô đang sửa: để con trỏ chữ hoạt động
                        e.preventDefault();
                        if (edit !== null) commit(edit);
                        setActive({ r, c });
                        setAnchor({ r, c });
                        setDrag({ a: { r, c }, b: { r, c } });
                        gridRef.current?.focus();
                      }}
                      onMouseEnter={() => drag && setDrag({ ...drag, b: { r, c } })}
                      onDoubleClick={() => startEdit(source({ r, c }))}
                    >
                      {isActive && edit !== null ? (
                        <input
                          className="cell-edit"
                          autoFocus
                          aria-label={`Sửa ô ${addr}`}
                          value={edit}
                          onChange={(e) => setEdit(e.target.value)}
                          onKeyDown={onEditKey}
                          onBlur={(e) => { if (!editDone.current) commit(e.currentTarget.value); }}
                        />
                      ) : text}
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

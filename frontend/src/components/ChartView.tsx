import * as XLSX from "xlsx";

/** Thông tin biểu đồ do backend đọc từ tệp (excel_inspect → sheets[].charts). */
export interface ChartInfo {
  type: "column" | "bar" | "line" | "pie" | string;
  title: string;
  anchor: string | null;
  series: { values: string | null; categories: string | null; name: string | null }[];
}

// Cùng bảng màu Okabe–Ito với backend: phân biệt được với người mù màu
const COLORS = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442"];
const W = 440;
const H = 220;
const M = { l: 40, r: 10, t: 10, b: 34 };

function splitRef(ref: string): [string | null, string] {
  const i = ref.lastIndexOf("!");
  if (i < 0) return [null, ref.replaceAll("$", "")];
  return [ref.slice(0, i).replace(/^'|'$/g, ""), ref.slice(i + 1).replaceAll("$", "")];
}

type Evaluate = (sheet: string, r: number, c: number, formula: string) => { value: unknown; error?: string; unsupported?: boolean };

/** Đọc các giá trị của một vùng ô trong workbook. Ô công thức được tính nếu có `evaluate`, không thì → null. */
export function readRange(wb: XLSX.WorkBook, ref: string | null, fallbackSheet: string, evaluate?: Evaluate): (string | number | null)[] {
  if (!ref) return [];
  const [sheetName, rng] = splitRef(ref);
  const ws = wb.Sheets[sheetName ?? fallbackSheet];
  if (!ws) return [];
  const r = XLSX.utils.decode_range(rng);
  const out: (string | number | null)[] = [];
  for (let row = r.s.r; row <= r.e.r; row++)
    for (let col = r.s.c; col <= r.e.c; col++) {
      const c = ws[XLSX.utils.encode_cell({ r: row, c: col })] as XLSX.CellObject | undefined;
      if (c?.f && evaluate) {
        const res = evaluate(sheetName ?? fallbackSheet, row, col, c.f);
        out.push(res.error || res.unsupported ? null : (res.value as string | number | null));
        continue;
      }
      out.push(c && c.t !== "z" && c.v !== undefined && c.v !== "" ? (c.v as string | number) : null);
    }
  return out;
}

export function ChartView({ chart, wb, sheet, evaluate }: { chart: ChartInfo; wb: XLSX.WorkBook; sheet: string; evaluate?: Evaluate }) {
  const series = chart.series.map((s, i) => ({
    name: String(readRange(wb, s.name, sheet, evaluate)[0] ?? `Chuỗi ${i + 1}`),
    values: readRange(wb, s.values, sheet, evaluate).map((v) => (typeof v === "number" ? v : Number(v) || 0)),
    color: COLORS[i % COLORS.length],
  }));
  const n = Math.max(0, ...series.map((s) => s.values.length));
  const cats = readRange(wb, chart.series[0]?.categories ?? null, sheet, evaluate).map((c, i) => String(c ?? i + 1));
  const labels = Array.from({ length: n }, (_, i) => cats[i] ?? String(i + 1));
  const title = chart.title || "Biểu đồ";
  const hasFormulaGaps = chart.series.some((s) => readRange(wb, s.values, sheet, evaluate).some((v) => v === null));

  return (
    <figure className="chart-card" aria-label={`${title}: biểu đồ ${chart.type}`}>
      <h4>{title} <span className="dim mono" style={{ fontSize: 11 }}>{chart.type} · {chart.anchor}</span></h4>
      <svg viewBox={`0 0 ${W} ${H}`} role="img">
        {chart.type === "pie" ? <Pie values={series[0]?.values ?? []} labels={labels} /> :
          <Axes series={series} labels={labels} kind={chart.type} />}
      </svg>
      <div className="chart-legend">
        {(chart.type === "pie" ? labels.map((l, i) => ({ name: l, color: COLORS[i % COLORS.length] })) : series).map((s) => (
          <span key={s.name}><i style={{ background: s.color }} />{s.name}</span>
        ))}
      </div>
      {hasFormulaGaps && <p className="hint">Ô công thức chưa có giá trị đã tính — mở bằng Excel để xem số chính xác.</p>}
    </figure>
  );
}

function Axes({ series, labels, kind }: { series: { values: number[]; color: string; name: string }[]; labels: string[]; kind: string }) {
  const all = series.flatMap((s) => s.values);
  const max = Math.max(0, ...all);
  const min = Math.min(0, ...all);
  const span = max - min || 1;
  const pw = W - M.l - M.r;
  const ph = H - M.t - M.b;
  const y = (v: number) => M.t + ph - ((v - min) / span) * ph;
  const n = labels.length || 1;
  const slot = pw / n;
  const ticks = [min, min + span / 2, max];
  const horizontal = kind === "bar";

  if (horizontal) {
    const sh = ph / n;
    const x = (v: number) => M.l + ((v - min) / span) * pw;
    const bh = (sh * 0.7) / series.length;
    return (
      <g>
        <line className="axis" x1={x(0)} x2={x(0)} y1={M.t} y2={M.t + ph} />
        {labels.map((l, i) => series.map((s, k) => (
          <rect key={`${i}-${k}`} x={Math.min(x(0), x(s.values[i] ?? 0))} y={M.t + i * sh + sh * 0.15 + k * bh}
            width={Math.abs(x(s.values[i] ?? 0) - x(0))} height={bh} fill={s.color} rx={2}>
            <title>{`${l} · ${s.name}: ${s.values[i] ?? 0}`}</title>
          </rect>
        )))}
        {labels.map((l, i) => <text key={l + i} x={M.l - 4} y={M.t + i * sh + sh / 2 + 3} textAnchor="end">{l.slice(0, 6)}</text>)}
      </g>
    );
  }
  const bw = (slot * 0.7) / series.length;
  return (
    <g>
      {ticks.map((t) => (
        <g key={t}>
          <line className="axis" x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} strokeDasharray={t === 0 ? undefined : "2 3"} />
          <text x={M.l - 4} y={y(t) + 3} textAnchor="end">{Number(t.toFixed(1)).toLocaleString("vi-VN")}</text>
        </g>
      ))}
      {kind === "line"
        ? series.map((s) => (
            <g key={s.name}>
              <polyline fill="none" stroke={s.color} strokeWidth={2}
                points={s.values.map((v, i) => `${M.l + slot * i + slot / 2},${y(v)}`).join(" ")} />
              {s.values.map((v, i) => <circle key={i} cx={M.l + slot * i + slot / 2} cy={y(v)} r={3} fill={s.color}><title>{`${labels[i]}: ${v}`}</title></circle>)}
            </g>
          ))
        : labels.map((l, i) => series.map((s, k) => {
            const v = s.values[i] ?? 0;
            return (
              <rect key={`${i}-${k}`} x={M.l + slot * i + slot * 0.15 + k * bw} y={Math.min(y(v), y(0))}
                width={bw} height={Math.abs(y(0) - y(v))} fill={s.color} rx={2}>
                <title>{`${l} · ${s.name}: ${v}`}</title>
              </rect>
            );
          }))}
      {labels.map((l, i) => (
        <text key={l + i} x={M.l + slot * i + slot / 2} y={H - M.b + 14} textAnchor="middle">
          {n > 8 && i % 2 ? "" : l.slice(0, 6)}
        </text>
      ))}
    </g>
  );
}

function Pie({ values, labels }: { values: number[]; labels: string[] }) {
  const total = values.reduce((a, b) => a + Math.max(b, 0), 0) || 1;
  const cx = W / 2;
  const cy = H / 2;
  const r = H / 2 - 12;
  let angle = -Math.PI / 2;
  return (
    <g>
      {values.map((v, i) => {
        const a = (Math.max(v, 0) / total) * Math.PI * 2;
        const x1 = cx + r * Math.cos(angle);
        const y1 = cy + r * Math.sin(angle);
        angle += a;
        const x2 = cx + r * Math.cos(angle);
        const y2 = cy + r * Math.sin(angle);
        return (
          <path key={i} d={`M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${a > Math.PI ? 1 : 0} 1 ${x2},${y2} Z`}
            fill={COLORS[i % COLORS.length]} stroke="var(--surface)" strokeWidth={1.5}>
            <title>{`${labels[i]}: ${v} (${Math.round((v / total) * 100)}%)`}</title>
          </path>
        );
      })}
    </g>
  );
}

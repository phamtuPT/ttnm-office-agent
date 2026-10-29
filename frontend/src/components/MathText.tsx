import katex from "katex";
import "katex/dist/katex.min.css";
import katexCss from "katex/dist/katex.min.css?inline";

export type MathPart = { kind: "text" | "inline" | "display"; value: string };

// Cùng quy tắc với backend (app/tools/omml.py, theo pandoc): sau $ mở và trước $ đóng không phải khoảng trắng,
// $ đóng không đứng ngay trước chữ số → "$100 và $200" vẫn là chữ thường. \$ = ký tự $.
const MATH = /\$\$(.+?)\$\$|(?<![\\$])\$([^\s$](?:[^$]*?[^\s\\$])?)\$(?!\d)/gs;

/** "Diện tích $S = \pi r^2$." → [chữ, công thức trong dòng, chữ]. */
export function splitMath(text: string): MathPart[] {
  const out: MathPart[] = [];
  let pos = 0;
  for (const m of text.matchAll(MATH)) {
    if (!/[\p{L}\p{N}_\\]/u.test(m[1] ?? m[2] ?? "")) continue; // "$...$" khi nói về cú pháp, không phải công thức
    const at = m.index ?? 0;
    if (at > pos) out.push({ kind: "text", value: text.slice(pos, at) });
    out.push(m[1] !== undefined ? { kind: "display", value: m[1].trim() } : { kind: "inline", value: m[2] });
    pos = at + m[0].length;
  }
  if (pos < text.length) out.push({ kind: "text", value: text.slice(pos) });
  return out.map((p) => (p.kind === "text" ? { ...p, value: p.value.replace(/\\\$/g, "$") } : p));
}

/**
 * Chuẩn bị Markdown cho remark-math: giữ $...$ là công thức, mọi dấu $ khác (giá tiền) thành \$ để không bị
 * hiểu nhầm. $$...$$ giữa câu đưa ra dòng riêng như remark-math yêu cầu.
 */
export function markdownWithMath(text: string): string {
  return splitMath(text)
    .map((p) => (p.kind === "text" ? p.value.replace(/\$/g, "\\$") : p.kind === "inline" ? `$${p.value}$` : `\n$$\n${p.value}\n$$\n`))
    .join("");
}

function Formula({ latex, display }: { latex: string; display: boolean }) {
  // throwOnError=false: LaTeX lỗi hiện màu đỏ thay vì làm hỏng cả khung
  const html = katex.renderToString(latex, { displayMode: display, throwOnError: false, output: "htmlAndMathml" });
  return <span className={display ? "math-display" : "math-inline"} dangerouslySetInnerHTML={{ __html: html }} />;
}

/**
 * Bản in Word: docx-preview dựng công thức thành MathML sơ sài (vỡ phân số, căn). Vẽ lại từng <math> bằng KaTeX
 * từ LaTeX backend đọc ra — chỉ khi số công thức khớp, nếu không giữ nguyên bản của docx-preview.
 */
export function replaceDocxMath(root: HTMLElement, equations: { latex: string; display: boolean }[]): boolean {
  const nodes = root.querySelectorAll("math");
  if (nodes.length === 0 || nodes.length !== equations.length) return false;
  nodes.forEach((node, i) => {
    const { latex, display } = equations[i];
    const host = document.createElement("span");
    host.className = display ? "math-display" : "math-inline";
    // Shadow DOM: CSS của docx-preview (".docx span { font-size: 11pt; white-space: pre-wrap }") làm vỡ bố cục KaTeX.
    // @font-face của KaTeX đã nạp ở trang chính nên font vẫn dùng được bên trong.
    const shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = `<style>${katexCss}</style>` +
      katex.renderToString(latex, { displayMode: display, throwOnError: false, output: "htmlAndMathml" });
    node.replaceWith(host);
  });
  return true;
}

/** Chữ thường có lẫn công thức $...$ (dàn ý Word/PowerPoint, lịch sử thay đổi). */
export function MathText({ text }: { text: string }) {
  const parts = splitMath(text);
  if (parts.every((p) => p.kind === "text")) return <>{text}</>;
  return (
    <>
      {parts.map((p, i) =>
        p.kind === "text" ? <span key={i}>{p.value}</span> : <Formula key={i} latex={p.value} display={p.kind === "display"} />,
      )}
    </>
  );
}

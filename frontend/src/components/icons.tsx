import { FileQuestion, FileSpreadsheet, FileText, Presentation, type LucideProps } from "lucide-react";
import type { FileKind } from "../types";

export const KIND_LABEL: Record<FileKind, string> = { xlsx: "Excel", docx: "Word", pptx: "PowerPoint" };
export const KIND_NOUN: Record<FileKind, string> = { xlsx: "Bảng tính", docx: "Tài liệu", pptx: "Bản trình chiếu" };

/** Icon loại tệp, tô màu theo loại (Excel xanh lá, Word xanh trời, PowerPoint san hô). */
export function FileKindIcon({ kind, ...props }: { kind: FileKind | null | undefined } & LucideProps) {
  const Icon = kind === "xlsx" ? FileSpreadsheet : kind === "docx" ? FileText : kind === "pptx" ? Presentation : FileQuestion;
  return <Icon className={`kind-icon ${kind ?? "none"}`} aria-hidden {...props} />;
}

/** Logo: tờ giấy gấp góc với tia nhấn — vẽ bằng SVG, không dùng chữ. */
export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 34 34" aria-hidden>
      <rect width="34" height="34" fill="var(--text)" />
      <path d="M9 7h11l5 5v15H9z" fill="var(--bg)" />
      <path d="M20 7v5h5" fill="none" stroke="var(--text)" strokeWidth="1.5" />
      <rect x="12" y="16" width="10" height="2" fill="var(--coral)" />
      <rect x="12" y="20" width="7" height="2" fill="var(--amber)" />
    </svg>
  );
}

/** Ảnh thu nhỏ minh hoạ cho thẻ chọn loại tệp và thẻ phiên gần đây. */
export function Thumb({ kind }: { kind: FileKind | null }) {
  if (kind === "xlsx")
    return (
      <svg className="thumb" viewBox="0 0 160 100" aria-hidden>
        <rect x="14" y="12" width="132" height="10" fill="var(--mint)" opacity="0.55" />
        {[0, 1, 2, 3, 4, 5].map((r) => (
          <g key={r}>
            {[0, 1, 2, 3].map((c) => (
              <rect key={c} x={14 + c * 33} y={24 + r * 11} width="32" height="10" fill="var(--thumb-cell)" />
            ))}
          </g>
        ))}
        <rect x="113" y="35" width="32" height="10" fill="var(--amber)" opacity="0.45" />
        <rect x="113" y="79" width="32" height="10" fill="var(--sky)" opacity="0.45" />
      </svg>
    );
  if (kind === "docx")
    return (
      <svg className="thumb" viewBox="0 0 160 100" aria-hidden>
        <rect x="40" y="6" width="80" height="94" fill="var(--thumb-page)" />
        <rect x="50" y="16" width="44" height="6" fill="var(--sky)" />
        {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
          <rect key={i} x="50" y={30 + i * 8} width={i % 3 === 2 ? 40 : 60} height="3" fill="var(--thumb-line)" />
        ))}
      </svg>
    );
  if (kind === "pptx")
    return (
      <svg className="thumb" viewBox="0 0 160 100" aria-hidden>
        <rect x="20" y="14" width="120" height="68" fill="var(--thumb-page)" />
        <rect x="30" y="24" width="56" height="7" fill="var(--coral)" />
        <rect x="30" y="38" width="40" height="3" fill="var(--thumb-line)" />
        <rect x="30" y="45" width="34" height="3" fill="var(--thumb-line)" />
        <rect x="30" y="52" width="38" height="3" fill="var(--thumb-line)" />
        {[22, 30, 16, 36].map((h, i) => (
          <rect key={i} x={88 + i * 11} y={72 - h} width="8" height={h} fill={i === 3 ? "var(--coral)" : "var(--amber)"} opacity={i === 3 ? 1 : 0.6} />
        ))}
      </svg>
    );
  return (
    <svg className="thumb" viewBox="0 0 160 100" aria-hidden>
      <rect x="40" y="14" width="80" height="72" fill="none" stroke="var(--border-strong)" strokeDasharray="5 4" />
      <path d="M80 62V38M70 48l10-10 10 10" fill="none" stroke="var(--coral)" strokeWidth="3" />
    </svg>
  );
}

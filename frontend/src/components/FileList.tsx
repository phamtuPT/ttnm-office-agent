import type { OfficeFile } from "../types";

const ICON = { xlsx: "📊", docx: "📄", pptx: "📽" };

interface Props {
  files: OfficeFile[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onUpload: (files: FileList) => void;
}

/** Dải tab các tệp trong phiên (tệp tải lên và tệp trợ lý tạo ra). */
export function FileList({ files, selectedId, onSelect, onUpload }: Props) {
  return (
    <nav className="file-tabs" aria-label="Tệp trong phiên">
      {files.map((f) => (
        <button key={f.id} className={`file-tab ${f.id === selectedId ? "active" : ""}`} onClick={() => onSelect(f.id)}
          aria-current={f.id === selectedId} title={`${f.name} — phiên bản ${f.current_version}`}>
          <span aria-hidden>{ICON[f.kind]}</span>
          <span className="name">{f.name}</span>
          <span className="ver">v{f.current_version}</span>
        </button>
      ))}
      <label className="btn primary upload" title="Tải lên .xlsx, .docx, .pptx">
        + Tải tệp
        <input type="file" accept=".xlsx,.docx,.pptx" multiple hidden
          onChange={(e) => { if (e.target.files) onUpload(e.target.files); e.target.value = ""; }} />
      </label>
    </nav>
  );
}

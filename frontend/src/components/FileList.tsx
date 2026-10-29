import type { OfficeFile } from "../types";

const ICON = { xlsx: "📊", docx: "📄", pptx: "📽" };

interface Props {
  files: OfficeFile[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onUpload: (files: FileList) => void;
}

export function FileList({ files, selectedId, onSelect, onUpload }: Props) {
  return (
    <div className="files">
      <label className="btn primary block">
        + Tải tệp lên
        <input type="file" accept=".xlsx,.docx,.pptx" multiple hidden
          onChange={(e) => { if (e.target.files) onUpload(e.target.files); e.target.value = ""; }} />
      </label>
      {files.length === 0 && <p className="hint">Chưa có tệp. Hỗ trợ .xlsx, .docx, .pptx.</p>}
      <ul>
        {files.map((f) => (
          <li key={f.id}>
            <button className={`file ${f.id === selectedId ? "active" : ""}`} onClick={() => onSelect(f.id)}>
              <span>{ICON[f.kind]}</span>
              <span className="name">{f.name}</span>
              <span className="ver">v{f.current_version}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

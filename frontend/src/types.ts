export type FileKind = "xlsx" | "docx" | "pptx";

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
}

export interface OfficeFile {
  id: string;
  name: string;
  kind: FileKind;
  current_version: number;
  latest_version: number;
}

/** Vùng người dùng chọn trên khung xem trước — agent chỉ được sửa trong vùng này. */
export interface Selection {
  file: string;
  sheet?: string;
  range?: string;
  paragraphs?: number[];
  slides?: number[];
}

export interface FileDiff {
  cells?: { sheet: string; ref: string; before: unknown; after: unknown }[];
  cells_total?: number;
  sheets_added?: string[];
  sheets_removed?: string[];
  paragraphs?: { op: string; before_index: number; after_index: number; before: string[]; after: string[] }[];
  slides?: { index: number; before: string | null; after: string | null }[];
}

export type ChatItem =
  | { kind: "text"; role: "user" | "model"; text: string; streaming?: boolean }
  | { kind: "tool"; id: string | null; name: string; args: Record<string, unknown>; status: "running" | "ok" | "error"; result?: Record<string, unknown> }
  | { kind: "change"; fileName: string; version: number; summary: string }
  | { kind: "notice"; text: string };

export interface ConfirmRequest {
  id: string;
  tool: string;
  args: Record<string, unknown>;
}

/** Sự kiện server → client. Đặc tả: docs/API.md */
export type ServerEvent =
  | { type: "turn.start" | "turn.end" | "turn.cancelled" }
  | { type: "message.delta"; text: string }
  | { type: "message.done"; text: string }
  | { type: "tool.start"; id: string | null; name: string; args: Record<string, unknown> }
  | { type: "tool.result" | "tool.error"; id: string | null; name: string; result: Record<string, unknown> }
  | { type: "file.changed"; file_id: string; file_name: string; version: number; summary: string; diff: FileDiff }
  | ({ type: "confirm.request" } & ConfirmRequest)
  | { type: "session.title"; title: string }
  | { type: "error"; message: string };

export const TOOL_LABELS: Record<string, string> = {
  list_files: "Xem danh sách tệp",
  excel_inspect: "Đọc cấu trúc bảng tính",
  excel_read_range: "Đọc vùng ô",
  excel_write_cells: "Ghi ô",
  excel_format_range: "Định dạng ô",
  excel_delete_sheet: "Xoá sheet",
  word_inspect: "Đọc dàn ý tài liệu",
  word_replace_paragraph: "Sửa đoạn văn",
  word_insert_paragraph: "Chèn đoạn văn",
  pptx_inspect: "Đọc dàn ý slide",
  pptx_set_text: "Sửa chữ trên slide",
};

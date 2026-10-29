export type FileKind = "xlsx" | "docx" | "pptx";

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  kind: FileKind | null; // loại của tệp đầu tiên trong phiên
  files: { id: string; name: string; kind: FileKind }[];
  message_count: number;
  preview: { file_id: string; version: number; kind: FileKind } | null; // tệp dùng làm ảnh xem trước
}

export interface OfficeFile {
  id: string;
  name: string;
  kind: FileKind;
  current_version: number;
  oldest_version: number;
  latest_version: number;
}

export interface FileVersion {
  number: number;
  source: string;
  summary: string;
  request: string;
  created_at: string;
  current: boolean;
  diff: FileDiff;
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
  created?: boolean;
  cells?: { sheet: string; ref: string; kind: "value" | "format"; before: unknown; after: unknown }[];
  values_total?: number;
  formats_total?: number;
  charts?: { sheet: string; before: number; after: number }[];
  sheets_added?: string[];
  sheets_removed?: string[];
  paragraphs?: { op: string; before_index: number; after_index: number; before: string[]; after: string[] }[];
  slides?: { index: number; before: string | null; after: string | null }[];
}

export type Provider = "gemini" | "openai" | "ollama" | "mock";

export interface ModelSet {
  agent: string;
  lite: string;
  fallback: string;
  stt: string;
}

export interface AppSettings {
  provider: Provider;
  models: Record<Provider, ModelSet>;
  ollama_base_url: string;
  pii_masking: boolean;
  has_key: { gemini: boolean; openai: boolean };
  render_available?: boolean;
}

export type ChatItem =
  | { kind: "text"; role: "user" | "model"; text: string; streaming?: boolean }
  | { kind: "tool"; id: string | null; name: string; args: Record<string, unknown>; status: "running" | "ok" | "error"; result?: Record<string, unknown> }
  | { kind: "change"; fileId: string; fileName: string; version: number; summary: string }
  | { kind: "notice"; text: string };

export interface ConfirmRequest {
  id: string;
  tool: string;
  args: Record<string, unknown>;
}

/** Sự kiện server → client. Đặc tả: docs/API.md */
export type ServerEvent =
  | { type: "turn.start"; turn_id: string; provider: string; model: string }
  | { type: "turn.end" | "turn.cancelled" }
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
  render_pages: "Tự kiểm tra bố cục bằng hình ảnh",
  undo_last_request: "Hoàn tác yêu cầu trước",
  excel_inspect: "Đọc cấu trúc bảng tính",
  excel_read_range: "Đọc vùng ô",
  excel_create_workbook: "Tạo bảng tính mới",
  excel_write_cells: "Ghi ô",
  excel_format_range: "Định dạng ô",
  excel_conditional_format: "Tô màu có điều kiện",
  excel_add_chart: "Thêm biểu đồ",
  excel_delete_sheet: "Xoá sheet",
  excel_sort_range: "Sắp xếp",
  excel_set_filter: "Bộ lọc",
  word_inspect: "Đọc dàn ý tài liệu",
  word_create_document: "Tạo tài liệu Word",
  word_replace_paragraph: "Sửa đoạn văn",
  word_insert_paragraph: "Chèn đoạn văn",
  word_insert_image: "Chèn ảnh vào Word",
  pptx_inspect: "Đọc dàn ý slide",
  pptx_create_presentation: "Tạo bài trình chiếu",
  pptx_set_text: "Sửa chữ trên slide",
  pptx_set_notes: "Ghi chú thuyết trình",
  pptx_add_image: "Chèn ảnh vào slide",
  pptx_add_slide: "Thêm slide",
  pptx_delete_slide: "Xoá slide",
  pptx_move_slide: "Đổi thứ tự slide",
  pptx_add_table: "Chèn bảng vào slide",
  pptx_add_chart: "Chèn biểu đồ vào slide",
  word_insert_table: "Chèn bảng Word",
  word_find_replace: "Tìm và thay",
  word_rewrite_paragraphs: "Viết lại các đoạn",
  word_add_comment: "Ghi nhận xét",
  word_suggest_edit: "Đề xuất sửa (Track Changes)",
  format_keywords: "Nhấn mạnh từ khoá",
  compare_versions: "So sánh phiên bản",
  compare_files: "So sánh hai tệp",
  image_edit: "Xử lý ảnh",
  ocr_image: "OCR cục bộ",
  run_python: "Chạy phân tích (sandbox)",
};

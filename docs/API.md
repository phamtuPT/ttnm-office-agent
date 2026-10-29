# Đặc tả API

Backend mặc định ở `http://localhost:8000`. Tài liệu OpenAPI tự sinh: `http://localhost:8000/docs`.

## REST

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/api/health` | Trạng thái, provider LLM đang dùng |
| POST | `/api/sessions` | Tạo phiên chat → `{id, title, created_at}` |
| GET | `/api/sessions` | Danh sách phiên (mới nhất trước) |
| GET | `/api/sessions/{sid}/messages` | Lịch sử hiển thị `[{id, role: user\|model, text}]` |
| POST | `/api/sessions/{sid}/files` | Tải tệp (multipart `file`) → `OfficeFile` |
| GET | `/api/sessions/{sid}/files` | Danh sách tệp của phiên |
| POST | `/api/sessions/{sid}/transcribe` | Giọng nói → văn bản (multipart `audio`) → `{text}` |
| GET | `/api/files/{fid}/content` | Tải nội dung bản làm việc hiện tại |
| GET | `/api/files/{fid}/outline` | Dàn ý: sheet+6 dòng đầu / các đoạn văn / các slide |
| GET | `/api/files/{fid}/versions` | Lịch sử phiên bản kèm diff |
| POST | `/api/files/{fid}/undo` | Hoàn tác (409 nếu không còn gì) |
| POST | `/api/files/{fid}/redo` | Làm lại (409 nếu không còn gì) |
| POST | `/api/files/{fid}/restore/{n}` | Quay về phiên bản n |

`OfficeFile = {id, name, kind: xlsx|docx|pptx, current_version, latest_version}`

Lỗi trả về dạng `{"detail": "thông báo tiếng Việt"}`.

## WebSocket `/ws/sessions/{sid}`

Phiên không tồn tại → đóng với mã `4404`.

### Client → server

```jsonc
{"type": "chat", "text": "Thêm dòng tổng", "images": [{"mime": "image/png", "data": "<base64>"}],
 "selection": {"file": "dt.xlsx", "sheet": "Doanh thu", "range": "B2:B10"}}   // selection có thể null
{"type": "confirm.response", "id": "<id từ confirm.request>", "approved": true}
{"type": "cancel"}                                                             // dừng lượt đang chạy
```

`selection` theo loại tệp: Excel `{file, sheet, range}`, Word `{file, paragraphs: [0, 2]}`,
PowerPoint `{file, slides: [1]}` (chỉ số từ 0).

### Server → client

| type | Trường | Ý nghĩa |
|---|---|---|
| `turn.start` | | Bắt đầu xử lý |
| `message.delta` | `text` | Một đoạn chữ model đang viết |
| `message.done` | `text`, `usage` | Câu trả lời hoàn chỉnh |
| `tool.start` | `id, name, args` | Bắt đầu gọi tool |
| `tool.result` / `tool.error` | `id, name, result` | Kết quả tool (`result.error` khi lỗi) |
| `file.changed` | `file_id, file_name, version, summary, diff` | Tệp vừa đổi → tải lại xem trước, tô màu diff |
| `confirm.request` | `id, tool, args` | Cần người dùng xác nhận thao tác phá huỷ (tự từ chối sau 120 s) |
| `session.title` | `title` | Tên phiên vừa được đặt tự động |
| `turn.cancelled` | | Lượt đã dừng theo yêu cầu |
| `error` | `message` | Lỗi hiển thị cho người dùng |
| `turn.end` | | Kết thúc lượt (luôn được gửi) |

Thứ tự điển hình:

```
turn.start → tool.start → tool.result → file.changed → message.delta… → message.done → turn.end → session.title
```

### Định dạng diff

```jsonc
// xlsx
{"cells": [{"sheet": "Doanh thu", "ref": "B5", "before": null, "after": "=SUM(B2:B4)"}],
 "cells_total": 1, "sheets_added": [], "sheets_removed": []}
// docx — các thao tác của difflib trên danh sách đoạn văn
{"paragraphs": [{"op": "replace", "before_index": 1, "after_index": 1, "before": ["cũ"], "after": ["mới"]}]}
// pptx — chữ của từng slide
{"slides": [{"index": 0, "before": "Tiêu đề\nCũ", "after": "Tiêu đề\nMới"}]}
```

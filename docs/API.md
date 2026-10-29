# Đặc tả API

Backend mặc định ở `http://localhost:8000`. Tài liệu OpenAPI tự sinh: `http://localhost:8000/docs`.
Lỗi trả về dạng `{"detail": "thông báo tiếng Việt"}`.

## REST

### Phiên

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/api/health` | `{ok: true}` |
| POST | `/api/sessions` | Tạo phiên → `{id, title, created_at}` |
| GET | `/api/sessions` | Danh sách phiên (mới nhất trước) |
| GET | `/api/sessions/{sid}/messages` | Lịch sử hiển thị `[{id, role: user\|model, text, turn_id}]` |
| POST | `/api/sessions/{sid}/undo-last` | Hoàn tác mọi thay đổi tệp của yêu cầu gần nhất (409 nếu không có) |
| GET | `/api/sessions/{sid}/turns` | Chỉ số từng yêu cầu: `status, steps, tool_calls, tool_errors, first_token_ms, duration_ms, input_tokens, output_tokens, provider, model` |
| GET | `/api/sessions/{sid}/assets` | Tên các ảnh đã gửi (`anh-1.jpg`, …) |
| GET | `/api/sessions/{sid}/assets/{name}` | Tải một ảnh |
| POST | `/api/sessions/{sid}/transcribe` | Giọng nói → văn bản (multipart `audio`) — dự phòng khi trình duyệt không có Web Speech API |

### Tệp và phiên bản

| Method | Đường dẫn | Mô tả |
|---|---|---|
| POST | `/api/sessions/{sid}/files` | Tải tệp (multipart `file`) → `OfficeFile` |
| GET | `/api/sessions/{sid}/files` | Danh sách tệp (cả tệp trợ lý tạo) |
| GET | `/api/files/{fid}/content` | Nội dung bản hiện tại |
| GET | `/api/files/{fid}/outline` | Dàn ý: sheet + 6 dòng đầu / các đoạn / các slide + ghi chú |
| GET | `/api/files/{fid}/pages` | Render trang/slide: `{available, pages, version}` (`available=false` nếu chưa có LibreOffice) |
| GET | `/api/files/{fid}/pages/{i}.png` | Ảnh trang/slide thứ i (gọi `/pages` trước) |
| GET | `/api/files/{fid}/versions` | Lịch sử (mới nhất trước): `[{number, request, summary, source, diff, current}]` |
| POST | `/api/files/{fid}/undo` | Lùi về phiên bản trước (= hoàn tác yêu cầu gần nhất trên tệp) |
| POST | `/api/files/{fid}/redo` | Tiến tới phiên bản sau |
| POST | `/api/files/{fid}/restore/{n}` | Khôi phục nội dung phiên bản n thành **phiên bản mới** (hoàn tác được) |

`OfficeFile = {id, name, kind: xlsx|docx|pptx, current_version, oldest_version, latest_version}`
— nút Hoàn tác bật khi `current > oldest`, Làm lại bật khi `current < latest`.

### Cài đặt

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/api/settings` | `{provider, models, ollama_base_url, pii_masking, has_key: {gemini, openai}, render_available}` |
| PUT | `/api/settings` | Sửa một phần, có hiệu lực từ yêu cầu chat kế tiếp |

```jsonc
// PUT /api/settings — mọi trường đều tuỳ chọn
{"provider": "ollama",
 "models": {"ollama": {"agent": "qwen3", "lite": ""}},
 "ollama_base_url": "http://localhost:11434/v1",
 "pii_masking": true,
 "api_keys": {"gemini": "AIza..."}}   // chỉ ghi; "" = xoá khoá đã lưu. Không bao giờ được trả về.
```

## WebSocket `/ws/sessions/{sid}`

Phiên không tồn tại → đóng với mã `4404`.

### Client → server

```jsonc
{"type": "chat",
 "text": "Tô đỏ các giá trị âm",
 "images": [{"mime": "image/jpeg", "data": "<base64>"}],          // tuỳ chọn
 "selection": {"file": "dt.xlsx", "sheet": "Doanh thu", "range": "B2:D10"},   // tuỳ chọn
 "active_file": "dt.xlsx"}                                          // tệp đang hiển thị = đối tượng mặc định
{"type": "confirm.response", "id": "<id từ confirm.request>", "approved": true}
{"type": "cancel"}                                                   // dừng lượt đang chạy
```

`selection` theo loại tệp: Excel `{file, sheet, range}`, Word `{file, paragraphs: [0, 2]}`,
PowerPoint `{file, slides: [1]}` (chỉ số từ 0).

### Server → client

| type | Trường | Ý nghĩa |
|---|---|---|
| `turn.start` | `turn_id, provider, model` | Bắt đầu xử lý |
| `message.delta` | `text` | Một đoạn chữ model đang viết |
| `message.done` | `text` | Câu trả lời hoàn chỉnh (thay cho các delta) |
| `tool.start` | `id, name, args` | Bắt đầu gọi tool |
| `tool.result` / `tool.error` | `id, name, result` | Kết quả tool (`result.error` khi lỗi) |
| `file.changed` | `file_id, file_name, version, summary, diff` | Tệp vừa đổi/được tạo → tải lại xem trước, tô màu diff |
| `confirm.request` | `id, tool, args` | Cần xác nhận thao tác phá huỷ (tự từ chối sau 120 s) |
| `session.title` | `title` | Tên phiên vừa được đặt |
| `turn.cancelled` | | Lượt đã dừng theo yêu cầu |
| `error` | `message` | Lỗi hiển thị cho người dùng |
| `turn.end` | `turn_id` | Kết thúc lượt (luôn được gửi) |

### Định dạng diff

```jsonc
// tệp mới
{"created": true}
// xlsx — kind: "value" (đổi giá trị/công thức) hoặc "format" (đổi định dạng)
{"cells": [{"sheet": "Doanh thu", "ref": "B14", "kind": "value", "before": null, "after": "=SUM(B2:B13)"}],
 "values_total": 1, "formats_total": 0,
 "charts": [{"sheet": "Doanh thu", "before": 0, "after": 1}],
 "conditional": [{"sheet": "Doanh thu", "before": 0, "after": 1}],
 "sheets_added": [], "sheets_removed": []}
// docx — so theo đoạn (gồm style và định dạng run)
{"paragraphs": [{"op": "replace", "before_index": 1, "after_index": 1, "before": ["cũ"], "after": ["mới"]}],
 "tables": {"before": 0, "after": 1}}
// pptx — slide có chữ, ghi chú hoặc vị trí hình thay đổi
{"slides": [{"index": 0, "before": "Tiêu đề\nCũ", "after": "Tiêu đề\nMới"}]}
```

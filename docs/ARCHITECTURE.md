# Kiến trúc hệ thống

Trợ lý AI dạng chat giúp chỉnh sửa tệp Word, Excel, PowerPoint. Người dùng ra lệnh bằng chữ, ảnh
hoặc giọng nói; agent (Gemini) gọi công cụ để sửa tệp, người dùng xem trước, thấy thay đổi và hoàn tác.

## Sơ đồ

```
┌──────────────────────── Frontend (React + Vite + TS) ────────────────────────┐
│ FileList │ PreviewPane (xlsx lưới ô / docx dàn ý + bản in / pptx thẻ slide)   │
│          │   ↳ chọn vùng sửa, tô màu ô/đoạn/slide vừa đổi, Hoàn tác/Làm lại   │
│ ChatPanel: stream chữ, bước tool, ảnh đính kèm, ghi âm, nút Dừng, xác nhận    │
└──────────────┬───────────────────────────────┬──────────────────────────────┘
          REST /api/...                   WebSocket /ws/sessions/{id}
               │                               │
┌──────────────▼───────────────────────────────▼──────────────────────────────┐
│ Backend FastAPI (backend/app)                                               │
│  api/         sessions, files (upload, outline, versions, undo/redo), ws    │
│  agent/       loop.py: model → tool → model … tối đa MAX_STEPS bước         │
│  llm/         base.py (giao diện) · gemini.py · mock.py                     │
│  tools/       registry · executor · excel · word · pptx · files             │
│  versioning/  store.py (bản chụp, undo/redo) · diff.py                      │
│  db.py        SQLAlchemy (SQLite)                                           │
└──────────────┬───────────────────────────────┬──────────────────────────────┘
        storage/app.db                  storage/<session>/files|versions
                                               │
                                    Gemini API (google-genai)
```

## Luồng một lượt chat

1. Frontend gửi `{"type":"chat", text, images, selection}` qua WebSocket.
2. `api/ws.py` ghép **khối ngữ cảnh** (danh sách tệp + vùng chọn) vào đầu tin nhắn, nạp lịch sử từ DB.
3. `agent/loop.py` gọi `provider.stream_turn()`. Chữ được đẩy ra ngay bằng sự kiện `message.delta`.
4. Nếu model gọi tool → `ToolExecutor.run()` cho từng lời gọi, **lần lượt** (không song song trên cùng tệp):
   1. tìm tool, kiểm tra tham số bằng Pydantic (lỗi → trả lại cho model tự sửa);
   2. tìm tệp, kiểm tra loại tệp và **vùng chọn**;
   3. tool phá huỷ (xoá sheet, …) → gửi `confirm.request`, chờ người dùng đồng ý;
   4. chạy handler trong thread, có **timeout**;
   5. tool ghi: tính **diff** với phiên bản hiện tại → có thay đổi thì lưu **phiên bản mới**,
      lỗi thì **rollback** bản làm việc.
5. Kết quả tool gửi lại cho model; lặp đến khi model trả lời bằng chữ (`message.done`).
6. Lưu toàn bộ lượt vào bảng `messages` (kể cả `raw` của Gemini). Lượt bị dừng/lỗi vẫn được lưu ở
   trạng thái hợp lệ kèm ghi chú.

## Các quyết định thiết kế

| Quyết định | Lý do |
|---|---|
| Tắt automatic function calling của SDK, tự viết vòng lặp | Cần chụp snapshot trước khi ghi, stream tiến trình, timeout, hỏi xác nhận |
| Lưu `raw` nội dung Gemini nguyên vẹn | Gemini 3+ bắt buộc gửi lại `thought_signature` ở lượt sau |
| Mỗi lần ghi = 1 phiên bản (bản chụp cả tệp) | Hoàn tác luôn đúng 100%, đơn giản, phù hợp tệp văn phòng cỡ nhỏ |
| Ghi sau khi undo → xoá nhánh redo | Giống hành vi undo quen thuộc (mô hình tư duy người dùng) |
| Tool chỉ trả tóm tắt (inspect) và đọc theo vùng | Không gửi cả tệp cho LLM → tiết kiệm token, ít bịa |
| Diff rỗng → cảnh báo cho model | Chặn trường hợp model nói "đã sửa xong" mà tệp không đổi |
| Vùng chọn được kiểm tra ở backend | Không chỉ dựa vào prompt — LLM có thể bỏ qua chỉ dẫn |
| System prompt cố định, ngữ cảnh đặt trong tin nhắn người dùng | Gemini cache ngầm phần đầu → rẻ hơn |
| `MockProvider` | Làm giao diện và chạy test không cần API key, không tốn tiền |
| Giọng nói → văn bản → người dùng sửa → mới gửi | Người dùng kiểm soát; tránh lỗi nhận dạng âm thầm thành lệnh sai |

## Bảo mật

- Chỉ nhận `.xlsx/.docx/.pptx`; kiểm tra là zip hợp lệ có `[Content_Types].xml`.
- Từ chối tệp chứa macro (`vbaProject.bin`), chặn zip bomb (tổng giải nén > 200 MB).
- Tên tệp được làm sạch (chặn path traversal); tool chỉ truy cập tệp trong phiên hiện tại.
- Giới hạn: tệp 20 MB, ảnh 5 MB, ghi âm 10 MB.
- `GEMINI_API_KEY` chỉ ở backend (`.env`, không commit).

## Việc còn để ngỏ (xem docs/PHAN_CONG.md)

- Tính lại công thức Excel bằng LibreOffice headless để phát hiện `#REF!`, `#NAME?` (giai đoạn 4).
- Thêm tool: bảng Word, slide mới/xoá/sắp xếp, ảnh trong slide, biểu đồ Excel, … (TV2).
- OCR cục bộ (PaddleOCR) để so sánh với Gemini vision trong báo cáo (TV3, giai đoạn 6).
- Xác thực người dùng: chưa có — bản demo chạy cục bộ.

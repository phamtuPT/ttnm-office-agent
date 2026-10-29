# Phân công và trạng thái

Bản gốc: [phân-công.docx](phân-công.docx). Trong file gốc cả 4 cột đều ghi tên "Tú" — nhóm cần sửa lại
tên thật. Tạm gọi TV1–TV4 theo thứ tự cột.

| | TV1 — Backend, agent | TV2 — HCI + công cụ Office | TV3 — Đa phương thức, tệp, hoàn tác | TV4 — UX/UI, frontend |
|---|---|---|---|---|
| **GĐ1** | Khảo sát, persona | Phân tích tác vụ, HTA | Nghiên cứu tương tác chữ/ảnh/giọng nói; tình huống AI xử lý sai | Nghiên cứu hệ thống tương tự; kiến trúc thông tin, luồng sử dụng |
| **GĐ2** | Yêu cầu chức năng; kiến trúc, API, DB ✅ | GOMS/KLM, baseline | Luồng tải tệp, ảnh, giọng nói; luồng kiểm tra và hoàn tác | Wireframe, prototype Figma; luồng chat, xem trước |
| **GĐ3** | FastAPI, WebSocket, LLM, vòng lặp agent ✅ khung | Công cụ Excel, Word 🟡 cơ bản | Quản lý tệp, sao lưu, lịch sử phiên ✅ khung | React: chat, danh sách tệp, xem trước ✅ khung |
| **GĐ4** | Tool calling, streaming, timeout, lỗi ✅ khung | Công cụ PowerPoint 🟡 cơ bản | Ảnh, giọng nói, hoàn tác, hiển thị thay đổi ✅ khung | Tích hợp API, trạng thái, chọn vùng, lỗi, hoàn tác ✅ khung |
| **GĐ5** | Kiểm thử agent, API, lỗi 🟡 | Kiểm thử công thức, định dạng, toàn vẹn tệp 🟡 | Kiểm thử OCR, lịch sử, hoàn tác, tệp lỗi, bảo mật 🟡 | Kiểm thử frontend; Nielsen, cognitive walkthrough; SUS |
| **GĐ6** | Báo cáo, Docker ✅ khung, tài liệu triển khai | Hoàn thiện công cụ; tổng hợp HTA, GOMS/KLM | Hoàn thiện đa phương thức; báo cáo OCR; phục hồi | Cải tiến giao diện; đánh giá khả dụng |

✅ khung = đã có code chạy được và test, cần hoàn thiện theo kết quả nghiên cứu · 🟡 = mới có phần cơ bản.
Các ô không đánh dấu là việc nghiên cứu/đánh giá do nhóm thực hiện.

## Mỗi thành viên bắt đầu từ đâu trong code

### TV1
- `backend/app/agent/loop.py`, `agent/prompts.py` — tinh chỉnh prompt theo các tình huống AI xử lý sai (TV3 GĐ1).
- `backend/app/llm/gemini.py` — đo `usage` thật, so với ước tính trong `docs/LLM_GEMINI.md`.
- TODO: tính lại công thức bằng LibreOffice headless (thêm vào `backend/Dockerfile`), trả lỗi `#REF!`… cho model.

### TV2
- Thêm tool vào `backend/app/tools/excel.py`, `word.py`, `pptx.py` theo mẫu có sẵn (`@tool(...)`, Pydantic args, `ToolError`).
- Tool ghi phải có `writes=True`; tool xoá dữ liệu thêm `destructive=True`.
- Gợi ý tool: Excel sắp xếp/lọc/biểu đồ; Word bảng, tìm-thay thế, định dạng chữ; PowerPoint thêm/xoá/sắp xếp slide, chèn ảnh.
- Viết test trong `backend/tests/test_tools.py`.
- Bảng `tool_calls` cho số liệu thời gian thật để đối chiếu GOMS/KLM.

### TV3
- `backend/app/versioning/` — sao lưu, diff, undo/redo (diff Word hiện chỉ so chữ, chưa so định dạng).
- `GeminiProvider.transcribe()` — so sánh chất lượng nhận dạng giọng nói tiếng Việt.
- TODO GĐ6: thêm `backend/app/media/ocr_paddle.py` để so PaddleOCR với Gemini vision trên cùng bộ ảnh.
- Kiểm thử bảo mật: `backend/tests/test_api.py` (macro, path traversal, tệp hỏng).

### TV4
- `frontend/src/components/` — ChatPanel, PreviewPane, FileList, ConfirmDialog, VoiceButton.
- Chạy với `LLM_PROVIDER=mock` để làm giao diện không cần API key.
- Áp thiết kế Figma; đánh giá Nielsen, cognitive walkthrough, SUS trên bản chạy thật.

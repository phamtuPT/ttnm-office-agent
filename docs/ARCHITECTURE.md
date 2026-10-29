# Kiến trúc hệ thống

**Đề tài:** Trợ lý AI tạo lập và chỉnh sửa tài liệu Office đa phương thức (Office AI Agent).
Bản đề xuất gốc: [đề-xuất-btl.docx](đề-xuất-btl.docx). Bảng đối chiếu đề xuất ↔ mã nguồn ở cuối tài liệu.

## Sơ đồ

Frontend có hai màn hình: **trang chủ** (chọn loại tệp để bắt đầu, danh sách phiên gần đây có ảnh xem trước) và
**không gian làm việc** của một phiên (sơ đồ dưới đây).

```
┌──────────────────────────── Frontend (React 18 + TypeScript + Vite) ─────────────────────────────┐
│ TRÁI: hội thoại                              │ PHẢI: tệp và xem trước                             │
│  • stream chữ, bước tool, kế hoạch ①→②→③     │  • tab tệp (tải lên + tệp trợ lý tạo)              │
│  • ảnh đính kèm / dán ảnh                    │  • Excel: lưới ô tự viết (SheetJS đọc), kéo chọn   │
│  • mic: Web Speech API → xem/sửa → Gửi       │  • Word: dàn ý chọn đoạn / bản in (docx-preview)   │
│  • Dừng, xác nhận thao tác phá huỷ           │  • PowerPoint: ảnh slide (LibreOffice) / dàn ý     │
│  • Hoàn tác yêu cầu vừa rồi, Cài đặt AI      │  • Hoàn tác / Làm lại / Lịch sử (diff, khôi phục)  │
└────────────────┬──────────────────────────────────────────────┬─────────────────────────────────┘
          REST /api/…                                  WebSocket /ws/sessions/{id}
┌────────────────▼──────────────────────────────────────────────▼─────────────────────────────────┐
│ Backend FastAPI (backend/app)                                                                    │
│  api/          sessions · files · settings · ws                                                  │
│  agent/        loop.py — vòng lặp ReAct tự cài đặt: LLM → tool → LLM …, giới hạn bước, timeout   │
│                prompts.py — system prompt + hướng dẫn thiết kế slide chỉ chèn khi liên quan PPTX │
│  llm/          base.py (giao diện) · gemini.py · openai_compat.py (OpenAI + Ollama) · mock.py    │
│  tools/        registry · executor (ghi nguyên tử, sao lưu) · excel · word · pptx · system       │
│  versioning/   store.py (thế hệ sao lưu, hoàn tác theo yêu cầu) · diff.py                        │
│  preview/      render.py — LibreOffice headless → PDF → PNG (PyMuPDF)                            │
│  privacy/      pii.py (ẩn danh tất định) · secrets.py (che khoá API trong log)                   │
│  media/        ocr.py — Tesseract cục bộ, CER, độ chính xác trích bảng                           │
│  runtime_settings.py — đổi nhà cung cấp/model/khoá lúc đang chạy                                 │
└───────┬───────────────────────────────┬───────────────────────────────┬─────────────────────────┘
   PostgreSQL (Alembic)          storage/<phiên>/files|versions|assets|renders     Gemini / OpenAI / Ollama
                                                                          sandbox (mạng nội bộ, không Internet)
```

## Luồng một yêu cầu (đề xuất mục 4.3)

1. Người dùng gõ hoặc nói (bản chép lời hiện trong ô soạn để sửa, **chỉ gửi khi bấm Gửi**), có thể đính
   kèm ảnh, kéo chọn vùng. Frontend gửi `{"type":"chat", text, images, selection, active_file}` qua WebSocket.
2. Backend tạo một **Turn** (yêu cầu), chuẩn hoá ảnh bằng Pillow và lưu thành `anh-N.jpg|png`, ghép
   **khối ngữ cảnh** (tệp trong phiên, tệp đang mở, vùng chọn, ảnh) vào đầu tin nhắn. Bật ẩn danh → che PII.
3. Agent nêu kế hoạch ngắn ①→②→③ rồi lặp: LLM chọn tool → `ToolExecutor` chạy → kết quả về LLM.
4. Mỗi tool ghi/tạo chạy trên **tệp tạm**; thành công mới `os.replace` → **ghi nguyên tử**. Mọi thay đổi
   trong cùng một yêu cầu gộp vào **một phiên bản** → hoàn tác một nhấp hoàn tác cả yêu cầu.
5. Với slide/trang: agent gọi `render_pages` để tự xem ảnh vừa làm, phát hiện chữ tràn/chồng lấn rồi sửa.
6. Token, sự kiện tool, thay đổi tệp, lỗi được stream về giao diện; khung xem trước tự tải lại và tô màu chỗ đổi.
7. Người dùng kiểm tra, yêu cầu tiếp, hoặc mở Lịch sử để xem khác biệt và khôi phục.

## Quyết định thiết kế

| Quyết định | Lý do |
|---|---|
| Vòng lặp ReAct tự viết trên SDK của từng hãng, **không dùng LangChain** | Kiểm soát trực tiếp `thought_signature` của Gemini, ảnh trong function response, retry/timeout; ít phụ thuộc. Giao diện `LLMProvider` là chỗ thay thế nếu nhóm muốn dùng LangChain Core |
| Một lớp `OpenAICompatProvider` cho cả OpenAI và Ollama | Ollama có API tương thích OpenAI (`/v1`), hỗ trợ tool calling |
| Lưu `raw` theo định dạng provider (`fmt`) | Gemini 3+ bắt buộc gửi lại thought_signature. Đổi provider giữa phiên → dựng lại lịch sử từ chữ |
| Tool ghi vào tệp tạm, `os.replace` khi xong | Ghi nguyên tử: lỗi/timeout/huỷ giữa chừng không làm hỏng tệp |
| Gộp thay đổi theo yêu cầu, giữ 20 thế hệ | Đề xuất: "hoàn tác theo từng yêu cầu", "sao lưu 20 thế hệ" |
| Khôi phục từ lịch sử tạo phiên bản mới | Đề xuất: "hoàn tác cả lần khôi phục" |
| Tool chỉ trả tóm tắt + đọc theo vùng | Không gửi cả tệp cho LLM → ít token, ít bịa |
| Diff gồm giá trị, định dạng, biểu đồ, định dạng có điều kiện | Phát hiện "nói đã sửa" mà tệp không đổi; hiển thị đúng chỗ thay đổi |
| Vùng chọn kiểm tra ở backend | Không chỉ dựa vào prompt — LLM có thể bỏ qua chỉ dẫn |
| Ẩn danh PII bằng regex + Luhn, đổi nhãn lại khi ghi tệp | Đề xuất: "thuật toán tất định, không đi qua LLM"; tệp kết quả vẫn đúng dữ liệu thật |
| Web Speech API, dự phòng ghi âm → máy chủ | Đề xuất chọn Web Speech; trình duyệt không hỗ trợ vẫn dùng được |
| LibreOffice tuỳ chọn | Không có thì giao diện dùng dàn ý, agent bỏ qua bước tự kiểm tra bằng hình |
| Biểu đồ Excel gốc, bảng màu Okabe–Ito | Biểu đồ gắn với ô; phân biệt được với người mù màu |

## Bảo mật

- Chỉ nhận `.xlsx/.docx/.pptx`, kiểm tra zip hợp lệ, từ chối macro (`vbaProject.bin`), chặn zip bomb.
- Tên tệp làm sạch (chặn path traversal); API không bao giờ trả đường dẫn máy chủ; tệp tạm `.tmp-*` không lộ ra.
- Khoá API chỉ ghi: `/api/settings` không bao giờ trả khoá; log được lọc chuỗi giống khoá (`AIza…`, `sk-…`, `Bearer …`).
- Docker chỉ mở cổng trên `127.0.0.1`.
- Giới hạn: tệp 20 MB, ảnh 10 MB, ghi âm 10 MB; mỗi tool có timeout; mỗi yêu cầu tối đa 10 bước.
- Gói miễn phí của Gemini dùng dữ liệu để cải thiện sản phẩm → thử nghiệm người dùng dùng gói trả phí, Ollama, hoặc tệp mẫu.

## Đối chiếu đề xuất ↔ mã nguồn

| Đề xuất | Trạng thái | Ở đâu |
|---|---|---|
| Khung chat trái, xem trước phải, chọn ô/đoạn/slide | ✅ | `frontend/src/App.tsx`, `components/PreviewPane.tsx` |
| Tệp đang hiển thị là đối tượng mặc định | ✅ | `active_file` trong `api/ws.py`, `agent/prompts.py` |
| Kế hoạch ①→②→③ cho tác vụ nhiều bước | ✅ (prompt) | `agent/prompts.py` |
| Excel: tạo bảng, công thức, định dạng, tô màu có điều kiện, biểu đồ gốc | ✅ | `tools/excel.py` |
| Excel: cảnh báo ghi đè ô có dữ liệu | ✅ | `excel_write_cells` |
| Excel: thanh sai số, sắp xếp, lọc | ✅ | `excel_add_chart(error_range)`, `excel_sort_range`, `excel_set_filter` |
| Excel: kiểm tra công thức trước khi ghi (#NAME?, #REF!, ngoặc), tự thêm `_xlfn.` cho hàm mới | ✅ | `tools/xlsx_util.py` |
| Word: tạo tài liệu, đề mục, danh sách, chèn ảnh, sửa đoạn | ✅ | `tools/word.py` |
| Word: bảng, tìm-thay hàng loạt, viết lại nhiều đoạn (dịch) | ✅ | `word_insert_table`, `word_find_replace`, `word_rewrite_paragraphs` |
| Word: Track Changes, Comment | ✅ | `word_suggest_edit`, `word_add_comment` |
| Word: sao chép phong cách từ tài liệu khác | ⬜ TV2 | |
| PowerPoint: tạo 16:9 có chủ đề màu, ghi chú, chèn ảnh, sửa chữ | ✅ | `tools/pptx.py` (theme clean/midnight/warm) |
| PowerPoint: thêm/xoá/đổi thứ tự slide, bảng, biểu đồ gốc | ✅ | `pptx_add_slide`, `pptx_delete_slide`, `pptx_move_slide`, `pptx_add_table`, `pptx_add_chart` |
| PowerPoint: mẫu thiết kế từ tệp `.pptx` có sẵn | ⬜ TV2 | |
| Định dạng từ khoá trên cả ba định dạng | ✅ | `tools/keywords.py` |
| Dịch giữ định dạng, so sánh hai phiên bản / hai tệp | ✅ | `word_rewrite_paragraphs`, `compare_versions`, `compare_files` |
| Tự render trang/slide để kiểm tra bố cục | ✅ (cần LibreOffice) | `preview/render.py`, tool `render_pages` |
| Ảnh → bảng Excel / văn bản Word | ✅ qua vision LLM | ảnh trong tin nhắn + tool tạo/ghi |
| Xử lý ảnh: xoay EXIF, thu nhỏ, nén; xoay/cắt/trắng đen theo yêu cầu | ✅ | `tools/assets.py`, tool `image_edit` |
| OCR cục bộ (Tesseract) + CER, độ chính xác trích bảng | ✅ (cần Tesseract, có trong Docker) | `media/ocr.py`, tool `ocr_image` |
| Ghi nguyên tử, 20 thế hệ, hoàn tác theo yêu cầu, hoàn tác lần khôi phục | ✅ | `tools/executor.py`, `versioning/store.py` |
| "Hoàn tác lần sửa vừa rồi" bằng lời | ✅ | tool `undo_last_request` |
| Ollama / OpenAI / Gemini, đổi trên giao diện không khởi động lại | ✅ | `llm/`, `runtime_settings.py`, `SettingsDialog.tsx` |
| Ẩn danh PII, che khoá API trong log | ✅ | `privacy/` |
| Retry backoff, timeout khi stream treo | ✅ | `llm/gemini.py`, `llm/base.py::with_idle_timeout` |
| `run_python` (pandas, statsmodels…) trong sandbox cách ly | ✅ | `sandbox/`, tool `run_python` |
| Web Speech API, xem/sửa bản chép trước khi gửi | ✅ | `components/VoiceButton.tsx` |
| Lưới Excel tự viết + biểu đồ SVG, chọn vùng | ✅ | `components/PreviewPane.tsx`, `components/ChartView.tsx` |
| Docker Compose, nginx, chỉ mở 127.0.0.1, cổng 3000 | ✅ | `docker-compose.yml` |
| Nhật ký vận hành, chỉ số mục 8.3 | ✅ | bảng `turns`, `tool_calls`; `GET /api/sessions/{id}/turns` |
| Bộ đánh giá tự động (tỉ lệ hoàn thành, độ chính xác tool, toàn vẹn tệp, độ trễ) | ✅ 12 yêu cầu mẫu, cần mở rộng lên ~100 | `backend/eval/` |
| pytest backend, độ phủ ≥ 70% | ✅ 85% (62 test) | `backend/tests` |
| Test frontend | ✅ 11 test (Vitest) | `frontend/src/__tests__` |
| Test end-to-end trình duyệt (Playwright) | ⬜ TV4 | |

### Sandbox `run_python`

Chạy mã do LLM sinh ra là rủi ro lớn nhất của hệ thống (nội dung tài liệu có thể chứa lệnh độc hại —
prompt injection). Mã **không bao giờ** chạy trong tiến trình backend:

- Dịch vụ `sandbox` riêng (`sandbox/app.py`): pandas, NumPy, SciPy, statsmodels, seaborn, matplotlib.
- Chỉ nối vào mạng nội bộ `sandboxnet` (`internal: true`) — không có đường ra Internet; user không phải root;
  hệ thống tệp chỉ đọc trừ `/tmp`; `mem_limit`, `cpus`, `pids_limit`, bỏ mọi capability.
- Mỗi lần chạy: thư mục tạm mới, giới hạn CPU/RAM/kích thước tệp/số tiến trình, timeout.
- Backend chỉ gửi **bản sao** các tệp được nêu tên; nhận lại stdout, hình (thành ảnh để chèn), bảng CSV,
  tệp Office (thành tệp mới trong phiên).
- Tool có `destructive=True`: người dùng **đọc mã và bấm Chạy** trước khi chạy.
- Không đặt `SANDBOX_URL` (chạy ngoài Docker) → tính năng tắt, trợ lý dùng công thức Excel thay thế.

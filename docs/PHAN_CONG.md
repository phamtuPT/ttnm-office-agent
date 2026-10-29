# Phân công và điểm bắt đầu trong mã nguồn

Theo mục 10 của [đề-xuất-btl.docx](đề-xuất-btl.docx) và lịch theo giai đoạn trong [phân-công.docx](phân-công.docx).
✅ = đã có mã chạy được và có test, cần hoàn thiện theo kết quả nghiên cứu · ⬜ = chưa làm.

## Đoàn Anh Minh — đặc tả, kiến trúc, backend hội thoại, điều phối AI

**HCI:** khảo sát, 2 persona, kịch bản và hành trình (Chương 4). **Phối hợp:** tích hợp, mốc bàn giao, tổng hợp báo cáo.

| Việc | Trạng thái | Mã nguồn |
|---|---|---|
| Kiến trúc, đặc tả API, DB | ✅ | `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/DATABASE.md` |
| PostgreSQL + migration Alembic, chuyển dữ liệu từ SQLite | ✅ | `backend/app/db.py`, `app/migrations/`, `scripts/` |
| Tài khoản đăng nhập (tuỳ chọn, máy chủ dùng chung), cách ly phiên theo người dùng | ✅ | `backend/app/auth.py`, `api/auth.py` |
| FastAPI, WebSocket, vòng lặp agent, streaming tiến trình | ✅ | `backend/app/api/ws.py`, `backend/app/agent/loop.py` |
| Đa nhà cung cấp (Gemini/OpenAI/Ollama), đổi lúc chạy | ✅ | `backend/app/llm/`, `backend/app/runtime_settings.py` |
| Retry, timeout, stream treo, xử lý lỗi model | ✅ | `backend/app/llm/gemini.py`, `llm/base.py` |
| Yêu cầu không rõ → hỏi lại; kế hoạch ①→②→③ | ✅ prompt, cần đánh giá | `backend/app/agent/prompts.py` |
| `run_python` trong sandbox cách ly | ✅ | `sandbox/`, `backend/app/tools/system.py` |
| Kiểm tra công thức trước khi ghi (#NAME?, #REF!) | ✅ | `backend/app/tools/xlsx_util.py` |
| Bộ đánh giá tự động mục 8.3 | ✅ 101 yêu cầu, 13 nhóm | `backend/eval/run_eval.py`, `cases.json` |
| Test điều phối, lỗi mô hình/timeout | ✅ một phần | `backend/tests/test_agent.py`, `test_llm_formats.py` |

## Lê Trọng Thức — HTA, GOMS/KLM, công cụ Office

**HCI:** ≥ 2 HTA có nhánh lỗi; GOMS/KLM một chuỗi thao tác (Chương 4, 7); đo thời gian thao tác thủ công.

| Việc | Trạng thái | Mã nguồn |
|---|---|---|
| Excel: tạo, đọc, ghi, định dạng, tô màu có điều kiện, biểu đồ gốc, xoá sheet | ✅ | `backend/app/tools/excel.py` |
| Excel: thanh sai số, sắp xếp, lọc, định dạng từ khoá | ✅ | `excel.py`, `keywords.py` |
| Word: tạo, dàn ý, sửa/chèn đoạn, chèn ảnh | ✅ | `backend/app/tools/word.py` |
| Word: bảng, sửa hàng loạt, Track Changes/Comment, định dạng từ khoá | ✅ | `word.py`, `keywords.py` |
| Word: sao chép phong cách từ tài liệu khác | ✅ | tool `word_copy_style` |
| Công thức toán Word/PowerPoint (LaTeX ⇄ OMML, sửa được trong Office) | ✅ | `backend/app/tools/omml.py`, `pptx_math.py` |
| PowerPoint: tạo 16:9, sửa chữ, ghi chú, chèn ảnh | ✅ | `backend/app/tools/pptx.py` |
| PowerPoint: chủ đề màu, bảng, biểu đồ gốc, thêm/xoá/sắp xếp slide | ✅ | `pptx.py` |
| PowerPoint: mẫu thiết kế từ tệp `default_theme.pptx`, bảng màu, mẫu của người dùng | ✅ | `app/tools/pptx_design.py`, `app/resources/` |
| PowerPoint: hình khối/sơ đồ; tự kiểm tra bố cục không cần LibreOffice (phát hiện 100%) | ✅ | `pptx_add_shape`, `app/tools/layout_check.py` |
| Bộ tệp mẫu + kết quả kỳ vọng (≈100 yêu cầu đánh giá) | ✅ 101 yêu cầu, 9 tệp đầu vào | `backend/eval/cases.json` |
| Test công thức, vùng sửa, định dạng, toàn vẹn tệp | ✅ một phần | `backend/tests/test_tools.py` |

Cách thêm tool: xem docstring `backend/app/tools/registry.py`. Tool ghi đặt `writes=True` (ghi vào `ctx.path`
là tệp tạm — executor tự lo ghi nguyên tử, sao lưu, diff); tool xoá dữ liệu thêm `destructive=True`.
Bảng `tool_calls` cho thời gian thật để đối chiếu GOMS/KLM.

## Phạm Đình Tú — luồng đa phương thức, tệp, lịch sử, hoàn tác, giọng nói

**HCI:** luồng văn bản/giọng nói/ảnh; xem/sửa bản chép lời trước khi gửi; kiểm tra và sửa dữ liệu AI đọc sai
(Chương 2, 3, 8).

| Việc | Trạng thái | Mã nguồn |
|---|---|---|
| Tải lên/tải xuống, kiểm tra tệp (macro, zip bomb, tên tệp) | ✅ | `backend/app/api/files.py` |
| Sao lưu 20 thế hệ, ghi nguyên tử, hoàn tác theo yêu cầu, khôi phục hoàn tác được | ✅ | `backend/app/versioning/store.py`, `tools/executor.py` |
| Diff giá trị/định dạng/biểu đồ/đoạn/slide | ✅ | `backend/app/versioning/diff.py` |
| Ảnh: chuẩn hoá (EXIF, thu nhỏ, nén), lưu, chèn vào tài liệu | ✅ | `backend/app/tools/assets.py` |
| Ảnh → bảng Excel / văn bản Word | ✅ qua vision LLM | luồng chat + tool tạo/ghi |
| Ảnh: cắt, xoay, thu nhỏ, trắng đen theo yêu cầu | ✅ | tool `image_edit` |
| OCR cục bộ (Tesseract), hàm CER và độ chính xác trích bảng | ✅ | `backend/app/media/ocr.py`, tool `ocr_image` |
| Bộ ~50 ảnh có nhãn + chạy đo CER | ✅ 50 ảnh tổng hợp; cần bổ sung ảnh chụp thật | `backend/eval/ocr_eval.py`, `ocr_dataset/` |
| Giọng nói: Web Speech API (vi-VN) + dự phòng máy chủ, không tự gửi | ✅ | `frontend/src/components/VoiceButton.tsx`, `/transcribe` |
| Bộ 10–15 câu lệnh giọng nói + bản chép chuẩn; đo lỗi nhận dạng | ✅ 15 câu, bản tổng hợp; cần thu giọng thật | `backend/eval/voice_eval.py`, `voice_dataset/` |
| Test tệp sai/hỏng, đường dẫn, ghi đè, khôi phục | ✅ | `backend/tests/test_api.py`, `test_tools.py` |

## Hoàng Văn Thái — kiến trúc thông tin, prototype, frontend, đánh giá khả dụng

**HCI:** wireframe, prototype Figma (có luồng mic và lỗi mic); lập luận thiết kế (Chương 3–5); Nielsen,
cognitive walkthrough, thử nghiệm người dùng, SUS (Chương 6).

| Việc | Trạng thái | Mã nguồn |
|---|---|---|
| Bố cục chat trái / xem trước phải, tab tệp | ✅ | `frontend/src/App.tsx`, `components/FileList.tsx` |
| Xem trước Excel (kéo chọn vùng), Word (dàn ý/bản in), PowerPoint (ảnh slide/dàn ý) | ✅ | `components/PreviewPane.tsx` |
| Lưới Excel: thanh công thức, dùng bàn phím, sửa ô trực tiếp; công thức toán bằng KaTeX | ✅ | `PreviewPane.tsx`, `components/MathText.tsx` |
| Phiếu SUS + trang tổng hợp, xuất CSV | ✅ | `pages/SusPage.tsx`, `backend/app/api/sus.py` |
| Vẽ biểu đồ Excel bằng SVG trong khung xem trước | ✅ | `components/ChartView.tsx` |
| Trang chủ chọn loại tệp + phiên gần đây, tab phiên, sáng/tối, kéo thả tệp, nhật ký tool | ✅ | `pages/HomePage.tsx`, `components/TopBar.tsx` |
| Trạng thái xử lý, bước tool, lỗi, Dừng, xác nhận | ✅ | `components/ChatPanel.tsx`, `ConfirmDialog.tsx` |
| Hoàn tác / Làm lại / Lịch sử có diff / Hoàn tác yêu cầu | ✅ | `components/HistoryDialog.tsx` |
| Nút mic, trạng thái đang nghe/đang nhận dạng, lỗi quyền mic, trình duyệt không hỗ trợ | ✅ | `components/VoiceButton.tsx` |
| Cài đặt mô hình AI | ✅ | `components/SettingsDialog.tsx` |
| Test thành phần frontend | ✅ 31 test | `frontend/src/__tests__` (Vitest) |
| Test end-to-end trình duyệt | ✅ 4 luồng (Playwright, `npm run e2e`) | `frontend/e2e/` |
| Đối chiếu với Figma, kiểm tra khả năng tiếp cận (bàn phím, trình đọc màn hình) | 🟡 lưới Excel, phiếu SUS, nút có nhãn; còn thử với trình đọc màn hình thật | `frontend/src/styles.css` |

Chạy giao diện không cần API key: để nhà cung cấp là **Thử nghiệm**, gõ “tạo bảng” hoặc “hoàn tác” để thử luồng.

## Mốc giọng nói (đề xuất)

Tuần 1 tìm hiểu nhu cầu · tuần 3 đặc tả + prototype · tuần 6 tích hợp nhận dạng tiếng Việt, giao diện mic, test ·
tuần 7 đánh giá với người dùng (so sánh nói và gõ) · tuần 8 hồi quy, hoàn thiện tài liệu.

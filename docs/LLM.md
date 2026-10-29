# Tầng LLM: Gemini, OpenAI, Ollama

Nhà cung cấp và model đổi được ngay trên giao diện (nút ⚙) mà không cần khởi động lại; `.env` chỉ là mặc định.
Đổi nhà cung cấp giữa một phiên: lịch sử được dựng lại từ phần chữ (bỏ chi tiết lời gọi tool cũ).

| Nhà cung cấp | Lớp | Khi nào dùng |
|---|---|---|
| Gemini | `llm/gemini.py` (SDK `google-genai`) | Mặc định — đọc ảnh tốt, tool calling ổn định |
| OpenAI | `llm/openai_compat.py` | So sánh chất lượng |
| Ollama (cục bộ hoặc cloud) | `llm/openai_compat.py` qua `http://<máy>:11434/v1` | Tài liệu nhạy cảm, dữ liệu không rời máy |
| Thử nghiệm | `llm/mock.py` | Làm giao diện, chạy test — không gọi mạng. Gõ “tạo bảng”, “hoàn tác” để thử luồng |

## Chỗ nào dùng LLM

| Việc | Model (Gemini, biến `.env`) |
|---|---|
| Vòng lặp agent: hiểu yêu cầu, lập kế hoạch, gọi tool, sinh nội dung, trả lời | `AGENT_MODEL=gemini-3.8-flash`, `AGENT_THINKING_LEVEL=low` (phản hồi đầu ~2,5 s thay vì ~5,5 s, xem docs/EVAL.md) |
| Đọc ảnh (hoá đơn, bảng giá, công văn) và tự xem ảnh slide vừa render | dùng chung `AGENT_MODEL` |
| Đặt tên phiên | `LITE_MODEL=gemini-3.5-flash-lite` |
| Giọng nói → văn bản (chỉ khi trình duyệt không có Web Speech API) | `STT_MODEL=gemini-3.5-flash-lite` |
| Dự phòng khi 429/503 | `FALLBACK_MODEL=gemini-3.5-flash-lite` |

**Không dùng LLM:** đọc/ghi tệp, diff, sao lưu/hoàn tác, render, ẩn danh PII, kiểm tra tệp, retry/timeout.

## Chi phí Gemini (tra ngày 29/10/2026)

Nguồn: [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing),
[Gemini models](https://ai.google.dev/gemini-api/docs/models). Kiểm tra lại trước khi viết báo cáo.

| Model | Giá / 1M token (vào → ra) |
|---|---|
| `gemini-3.8-flash` | $0.75 → $3.75, **từ 01/01/2027: $1.50 → $7.50** |
| `gemini-3.5-flash-lite` | $0.30 → $2.50 |

Ước tính một yêu cầu ≈ 4 lần gọi model, mỗi lần ~8k token vào và ~1.5k token ra:

| | Giá hiện tại | Từ 01/01/2027 |
|---|---|---|
| 1 yêu cầu | ~$0.05 | ~$0.10 |
| 1 yêu cầu có cache ngầm (~70% đầu vào trùng) | ~$0.03 | ~$0.06 |
| Bộ đánh giá 100 yêu cầu × 3 lần chạy | ~$9–15 | ~$18–30 |
| Thử nghiệm người dùng (15 người × 6 tác vụ × 4 lượt) | ~$11–18 | ~$22–36 |

Số liệu thật nằm trong bảng `turns` (`input_tokens`, `output_tokens`) — dùng để thay ước tính trong báo cáo.

> **Gói miễn phí:** Google dùng dữ liệu gửi lên để cải thiện sản phẩm. Khi thử nghiệm với người dùng
> thật hãy dùng gói trả phí, Ollama, hoặc chỉ dùng tệp mẫu — ghi điểm này vào phần đạo đức nghiên cứu.

## Những điểm dễ sai (đã xử lý)

1. **Tắt automatic function calling** của SDK — tự chạy tool để kịp sao lưu, stream tiến trình, timeout, hỏi xác nhận.
2. **Gemini: giữ nguyên `thought_signature`** — nối nguyên `Content` model trả về vào lịch sử; lưu bằng
   `model_dump(mode="json")` (bytes → base64), nạp lại bằng `Content.model_validate`.
3. **Stream:** giữ mọi `Part` theo thứ tự (kể cả part rỗng chỉ mang chữ ký); OpenAI/Ollama gom
   `tool_calls` theo `index` vì tham số đến từng mảnh.
4. **Ảnh trong kết quả tool** (`render_pages`): Gemini gửi kèm trong `FunctionResponse.parts`;
   OpenAI/Ollama gửi thêm một tin nhắn người dùng chứa ảnh ngay sau tin nhắn `tool`.
5. **Retry:** Gemini 429/500/503/504 → thử lại 1 s, 2 s, 4 s rồi chuyển `FALLBACK_MODEL`; không thử lại khi
   đã stream chữ (tránh lặp chữ). OpenAI SDK tự retry 3 lần.
6. **Stream treo:** quá `STREAM_IDLE_TIMEOUT_S` giây không nhận được gói nào → báo lỗi thay vì chờ mãi.
7. **Tham số tool không phải JSON** (hay gặp ở mô hình nhỏ chạy Ollama): báo lỗi lại cho model tự sửa.

## Viết tool tốt cho LLM

- Mô tả tool và từng `Field` bằng tiếng Việt, nói rõ khi nào dùng ("Luôn gọi trước khi sửa").
- Thông báo lỗi (`ToolError`) phải chỉ cách sửa: "Không có sheet 'X'. Các sheet hiện có: [...]".
- Giới hạn kích thước kết quả (số ô, số đoạn) để không tràn ngữ cảnh.
- Mô hình nhỏ chạy cục bộ chọn tool kém hơn khi có quá nhiều tool → hướng dẫn chuyên biệt (như thiết kế
  slide) chỉ chèn vào prompt khi liên quan (`agent/prompts.py`).

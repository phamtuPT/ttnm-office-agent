# Dùng Gemini cho tầng LLM

Số liệu giá và tên model tra từ [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) và
[Gemini models](https://ai.google.dev/gemini-api/docs/models) ngày 29/10/2026. Kiểm tra lại trước khi
viết báo cáo vì giá thay đổi thường xuyên.

## Chỗ nào dùng LLM

| Việc | Model (biến `.env`) | Giá / 1M token (vào → ra) |
|---|---|---|
| Vòng lặp agent: hiểu yêu cầu, gọi tool, sinh nội dung, trả lời | `AGENT_MODEL=gemini-3.8-flash` | $0.75 → $3.75 (**từ 01/01/2027: $1.50 → $7.50**) |
| Hiểu ảnh / OCR (ảnh nằm trong tin nhắn chat) | dùng chung `AGENT_MODEL` | như trên |
| Đặt tên phiên | `LITE_MODEL=gemini-3.5-flash-lite` | $0.30 → $2.50 |
| Giọng nói → văn bản | `STT_MODEL=gemini-3.5-flash-lite` | khoảng 2k token/phút audio |
| Dự phòng khi 429/503 | `FALLBACK_MODEL=gemini-3.5-flash-lite` | |

Có thể thử `STT_MODEL=gemini-3.5-transcribe` (model chuyên chép giọng nói, khoảng $0.005/phút) —
**chưa kiểm chứng** model này có gọi được qua `generate_content` hay không.

**Không cần LLM:** đọc/ghi tệp, tính diff, sao lưu/hoàn tác, xem trước, kiểm tra tệp, timeout/retry.

## Ước tính chi phí

Giả định một lượt chat ≈ 4 lần gọi model, mỗi lần ~8k token vào (prompt + mô tả tool 3k, lịch sử 2k,
kết quả tool 3k) và ~1.5k token ra (kể cả token suy nghĩ).

| | Giá hiện tại | Từ 01/01/2027 |
|---|---|---|
| 1 lượt | ~$0.05 | ~$0.10 |
| 1 lượt có cache ngầm (~70% đầu vào trùng) | ~$0.03 | ~$0.06 |
| Phát triển + test (~2.000 lượt) | ~$60–100 | ~$120–200 |
| Thử nghiệm người dùng (10 người × 5 tác vụ × 4 lượt) | ~$6–10 | ~$12–20 |

Giảm chi phí:
- Phát triển giao diện và chạy test với `LLM_PROVIDER=mock`.
- Tool chỉ trả tóm tắt; model đọc chi tiết bằng `excel_read_range` khi cần.
- `MAX_STEPS=8` chặn vòng lặp vô hạn.

> **Gói miễn phí:** Google dùng dữ liệu gửi lên để cải thiện sản phẩm. Khi thử nghiệm với người dùng
> thật hãy dùng gói trả phí hoặc chỉ dùng tệp mẫu — ghi điểm này vào phần đạo đức nghiên cứu.

## Những điểm dễ sai (đã xử lý trong `backend/app/llm/gemini.py`)

1. **Tắt automatic function calling** (`AutomaticFunctionCallingConfig(disable=True)`) — tự chạy tool để
   kịp snapshot, stream tiến trình, timeout, hỏi xác nhận.
2. **Giữ nguyên `thought_signature`**: nối nguyên `Content` model trả về vào lịch sử; lưu DB bằng
   `model_dump(mode="json")` (bytes → base64) và nạp lại bằng `Content.model_validate`.
   Không tự dựng lại tin nhắn model từ chữ.
3. **Stream:** giữ mọi `Part` theo thứ tự, kể cả part rỗng chỉ mang chữ ký.
4. **Retry:** 429/500/503/504 → thử lại (1 s, 2 s, 4 s) rồi chuyển `FALLBACK_MODEL`. Không thử lại nếu
   đã stream chữ cho người dùng (tránh lặp chữ).
5. **Khai báo tool:** dùng `parameters_json_schema`; schema Pydantic được inline `$defs` và bỏ `title`.
6. **Kết quả tool** gửi lại dạng `FunctionResponse` kèm đúng `id` của lời gọi.

## Viết tool tốt cho Gemini

- Mô tả tool và từng `Field` bằng tiếng Việt, nói rõ khi nào dùng ("Luôn gọi trước khi sửa").
- Thông báo lỗi (`ToolError`) phải chỉ cách sửa: "Không có sheet 'X'. Các sheet hiện có: [...]".
- Giới hạn kích thước kết quả (số ô, số đoạn) để không tràn ngữ cảnh.

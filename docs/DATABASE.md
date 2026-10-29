# Cơ sở dữ liệu

SQLite (`storage/app.db`), SQLAlchemy 2. Bảng được tạo tự động khi backend khởi động (`init_db`).
Chưa dùng migration — **đổi schema thì xoá `storage/app.db`** khi phát triển.
Định nghĩa: `backend/app/db.py`.

```
chat_sessions 1──* turns            (mỗi yêu cầu của người dùng)
              1──* messages ──> turn
              1──* files 1──* file_versions ──> turn
              1──* tool_calls ──> turn
app_settings                        (cài đặt đổi lúc chạy)
```

| Bảng | Cột chính | Ghi chú |
|---|---|---|
| `chat_sessions` | `id`, `title`, `pii_map` | `pii_map`: nhãn ⟦EMAIL_1⟧ → giá trị thật, không bao giờ gửi cho LLM |
| `turns` | `request`, `status`, `provider`, `model`, `steps`, `tool_calls`, `tool_errors`, `first_token_ms`, `duration_ms`, `input_tokens`, `output_tokens`, `error` | Chỉ số kỹ thuật mục 8.3 của đề xuất |
| `messages` | `turn_id`, `seq`, `role` (user/model/tool), `text`, `fmt`, `raw` | `raw` = nội dung gốc gửi LLM theo định dạng `fmt` (gemini/openai/mock), **giữ nguyên** (thought_signature). `text` = bản hiển thị đã bỏ ẩn danh |
| `files` | `name`, `kind`, `current_version` | Tên duy nhất trong phiên |
| `file_versions` | `number`, `turn_id`, `source`, `summary`, `diff` | Một phiên bản / yêu cầu. `source`: `upload`, `restore` hoặc tên các tool |
| `tool_calls` | `turn_id`, `name`, `args`, `ok`, `result`, `duration_ms` | Nhật ký để đo độ chính xác gọi tool |
| `app_settings` | `key`, `value` | Nhà cung cấp, model, khoá API (khoá lưu cục bộ, API không trả về) |

## Lưu tệp trên đĩa

```
storage/<session_id>/files/<tên tệp>                    bản làm việc (workspace)
storage/<session_id>/files/.tmp-*                       tệp tạm khi tool đang ghi (ghi nguyên tử)
storage/<session_id>/versions/<file_id>/v<n>.ext        thế hệ sao lưu (.history), tối đa 20
storage/<session_id>/assets/anh-<n>.jpg|png             ảnh người dùng gửi (đã chuẩn hoá)
storage/<session_id>/renders/<file_id>/v<n>/page-*.png  ảnh trang/slide (cache theo phiên bản)
```

## Truy vấn cho báo cáo đánh giá (mục 8.3)

```sql
-- Độ trễ, số bước, tỉ lệ hoàn thành theo model
SELECT provider, model, COUNT(*) AS so_yeu_cau,
       AVG(status = 'done') AS ti_le_xong,
       AVG(first_token_ms) AS token_dau_ms, AVG(duration_ms) AS tong_ms,
       AVG(steps) AS so_buoc_tb, SUM(input_tokens) AS token_vao, SUM(output_tokens) AS token_ra
FROM turns GROUP BY provider, model;

-- Độ chính xác gọi tool (tool call hợp lệ, đúng tham số / tổng)
SELECT name, COUNT(*) AS so_lan, AVG(ok) AS ti_le_ok, AVG(duration_ms) AS ms_tb
FROM tool_calls GROUP BY name ORDER BY so_lan DESC;
```

# Cơ sở dữ liệu

SQLite (`storage/app.db`), SQLAlchemy 2. Bảng được tạo tự động khi backend khởi động (`init_db`).
Định nghĩa: `backend/app/db.py`.

```
chat_sessions 1──* messages
              1──* files 1──* file_versions
              1──* tool_calls
```

| Bảng | Cột chính | Ghi chú |
|---|---|---|
| `chat_sessions` | `id`, `title`, `created_at` | Tên phiên do model lite đặt sau tin nhắn đầu |
| `messages` | `session_id`, `seq`, `role` (user/model/tool), `text`, `raw` (JSON) | `raw` = nội dung gốc gửi cho LLM, **phải giữ nguyên** (thought_signature). `text` chỉ để hiển thị |
| `files` | `session_id`, `name`, `kind`, `current_version` | Tên duy nhất trong phiên |
| `file_versions` | `file_id`, `number`, `source`, `summary`, `diff` (JSON) | `source` = `upload` hoặc tên tool đã tạo ra phiên bản |
| `tool_calls` | `session_id`, `name`, `args`, `ok`, `result`, `duration_ms` | Nhật ký để kiểm thử, đo thời gian, viết báo cáo |

## Lưu tệp trên đĩa

```
storage/<session_id>/files/<tên tệp>              bản làm việc — tool đọc/ghi trực tiếp
storage/<session_id>/versions/<file_id>/v<n>.ext   bản chụp; v1 là bản tải lên
```

- Ghi thành công → chụp bản làm việc thành `v<current+1>`.
- Hoàn tác/làm lại/khôi phục → chép `v<n>` đè lên bản làm việc, đổi `current_version`.
- Ghi mới khi đang ở phiên bản cũ → xoá các phiên bản phía sau.

## Truy vấn hữu ích cho báo cáo

```sql
-- Tỉ lệ lỗi và thời gian trung bình theo tool
SELECT name, COUNT(*) AS so_lan, AVG(ok) AS ti_le_ok, AVG(duration_ms) AS ms_tb
FROM tool_calls GROUP BY name ORDER BY so_lan DESC;
```

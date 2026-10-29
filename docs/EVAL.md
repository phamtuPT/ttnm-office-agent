# Kết quả đánh giá tự động

Bộ đánh giá: `backend/eval/` (12 yêu cầu mẫu trong `cases.json`, chấm tự động bằng kiểm tra trên tệp kết quả).
Chạy lại: `cd backend && python -m eval.run_eval --provider gemini --repeat 3`. CSV chi tiết lưu ở `backend/eval/results/`.

## Lần chạy 29/10/2026 — Gemini `gemini-3.8-flash`, 1 lượt

| Chỉ số (đề xuất mục 8.3) | Kết quả | Mục tiêu |
|---|---|---|
| Tỉ lệ hoàn thành tác vụ | **100%** (12/12) | ≥ 85% |
| Độ chính xác gọi tool | **100%** (36/36 lời gọi hợp lệ) | ≥ 90% |
| Tính toàn vẹn tệp | **100%** | 100% |
| Số bước trung bình | **3,1** | ≤ 10 |
| Thời gian tới token đầu (trung bình) | 8,0 s | < 5 s — **chưa đạt** |
| Thời gian hoàn thành (trung bình) | 19,5 s | < 60 s |
| Token vào / ra | 315.832 / 14.303 | — |
| Chi phí ước tính | ≈ $0,29 (giá trước 01/01/2027) | — |

| Yêu cầu | Nhóm | Kết quả | Bước | Chuỗi tool |
|---|---|---|---|---|
| Tạo bảng 12 tháng + tổng + biểu đồ | Excel | Đạt | 4 | create_workbook, format_range ×2, add_chart, inspect |
| Tô đỏ giá trị âm trong vùng chọn | Sửa một phần | Đạt | 3 | inspect, conditional_format |
| Thêm dòng Tổng | Excel | Đạt | 3 | inspect, write_cells, format_range |
| Sắp xếp theo Q1 giảm dần | Excel | Đạt | 4 | inspect, sort_range, read_range |
| Soạn báo cáo 3 đề mục | Word | Đạt | 2 | create_document |
| Thay "khách hàng" → "đối tác" | Word | Đạt | 3 | inspect, find_replace |
| Rà soát bằng Track Changes + nhận xét | Rà soát | Đạt | 3 | inspect, suggest_edit, add_comment |
| Dịch sang tiếng Anh giữ số, ngày | Dịch | Đạt | 3 | inspect, rewrite_paragraphs |
| 5 slide có ghi chú | PowerPoint | Đạt | 5 | create_presentation, render_pages, inspect, set_text |
| In đậm, tô cam từ khoá trên slide | Định dạng từ khoá | Đạt | 3 | inspect, format_keywords, render_pages |
| "Hoàn tác lần sửa vừa rồi" | Hoàn tác | Đạt | 2 | undo_last_request |
| "Sửa cái bảng kia đi" (mơ hồ) | Yêu cầu không rõ | Đạt — hỏi lại, không sửa tệp | 2 | inspect |

## Những gì bộ đánh giá đã giúp phát hiện và sửa

Lần chạy đầu (sau khi sửa lỗi của chính bộ đánh giá) đạt 10/12. Hai lỗi thật của agent:

1. **Rà soát hợp đồng:** nhận xét vào đoạn vừa đề xuất sửa báo "Đoạn trống", và `word_inspect` hiện đoạn có Track Changes
   là chuỗi rỗng → agent tưởng đoạn bị xoá, gọi hoàn tác rồi sửa thẳng nội dung (trái quy tắc rà soát). Đã sửa: đọc chữ
   theo dạng "chấp nhận mọi đề xuất", báo `pending_suggestion`, nhận xét được đoạn có Track Changes.
2. **Làm 5 slide:** agent sửa chữ từng shape một → vượt 10 bước. Đã sửa: `pptx_set_text`, `word_suggest_edit`,
   `word_add_comment` nhận nhiều mục một lần; prompt hướng dẫn gộp thay đổi và gọi tool song song. Số bước trung bình
   giảm từ 4,3 xuống 3,1.

## Hạn chế của lần đánh giá này

- Mới 12 yêu cầu × 1 lượt: cần mở rộng lên ~100 yêu cầu và chạy 3 lượt để có số liệu đủ tin cậy cho báo cáo.
- Máy chạy đánh giá chưa có LibreOffice nên bước tự kiểm tra bố cục slide (`render_pages`) chỉ trả "chưa cài".
- Chưa đánh giá OCR (CER) vì chưa có bộ ảnh có nhãn.
- Thời gian tới token đầu 8 s vượt mục tiêu 5 s: phần lớn do model suy nghĩ trước lời gọi tool đầu tiên. Hướng xử lý:
  giảm mức suy nghĩ (`thinking_level`) cho model agent, hoặc hiển thị trạng thái "đang lập kế hoạch" ngay khi gửi.

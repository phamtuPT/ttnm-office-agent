# Kết quả đánh giá tự động

Bộ đánh giá: `backend/eval/` (12 yêu cầu mẫu trong `cases.json`, chấm tự động bằng kiểm tra trên tệp kết quả).
Chạy lại: `cd backend && python -m eval.run_eval --provider gemini --repeat 3`. CSV chi tiết lưu ở `backend/eval/results/`.

**Token đầu** = thời gian từ lúc gửi yêu cầu tới phản hồi đầu tiên của model hiện lên giao diện: chữ (thường là dòng
kế hoạch ①→②→③) hoặc bước tool đầu tiên. Cả hai đều hiện ngay cho người dùng.

## Kết quả hiện tại — 29/10/2026, Gemini `gemini-3.8-flash`, mức suy nghĩ `low`, 2 lượt × 12 yêu cầu

| Chỉ số (đề xuất mục 8.3) | Kết quả | Mục tiêu |
|---|---|---|
| Tỉ lệ hoàn thành tác vụ | **100%** (24/24) | ≥ 85% |
| Độ chính xác gọi tool | **100%** | ≥ 90% |
| Tính toàn vẹn tệp | **100%** | 100% |
| Số bước trung bình | **2,75** | ≤ 10 |
| Token đầu — trung bình | **4,3 s** | < 5 s |
| Token đầu — trung vị / p90 / tối đa | 2,3 s / 9,6 s / 12,5 s | — |
| Số lần token đầu ≤ 5 s | 18/24 | — |
| Thời gian hoàn thành trung bình | **12,9 s** | < 60 s |
| Token vào / ra (24 lần chạy) | 545.284 / 11.899 | — |
| Chi phí ước tính (24 lần chạy) | ≈ $0,45 (giá trước 01/01/2027) | — |

Các lần chạy chậm hơn 5 s không gắn với một loại yêu cầu cố định: cùng một yêu cầu (ví dụ "tô đỏ giá trị âm") lượt 1 mất
2,0 s, lượt 2 mất 11,4 s. Phần chênh này là do độ trễ dao động phía máy chủ Gemini, không phải do agent.

## So sánh trước / sau tối ưu độ trễ

| | Trước: suy nghĩ mặc định | Sau: suy nghĩ `low` + kiểm tra giữ số |
|---|---|---|
| Lượt chạy | 1 × 12 | 2 × 12 |
| Tỉ lệ hoàn thành | 100% | 100% |
| Độ chính xác gọi tool | 100% | 100% |
| Số bước trung bình | 3,1 | 2,75 |
| Thời gian hoàn thành trung bình | 19,5 s | 12,9 s |
| Token ra (trung bình / lần chạy) | ≈ 1.190 | ≈ 500 |

Đo riêng lượt gọi model đầu tiên cho cùng một yêu cầu, cùng prompt và cùng bộ tool:

| Mức suy nghĩ | Phản hồi đầu tiên | Hết lượt gọi | Token suy nghĩ |
|---|---|---|---|
| Mặc định | 5,3–5,8 s | 5,9 s | 360–500 |
| `low` | 2,2–2,7 s | 3,1–3,6 s | 0 |
| `minimal` | model không hỗ trợ | — | — |

Cách đo cũ chỉ tính khi có **chữ** xuất hiện. Khi lượt đầu của model chỉ là lời gọi tool, đồng hồ chạy qua cả bước thực
thi tool, nên con số "8,0 s" của lần đánh giá trước bị đội lên: có một lần lên tới 39,6 s. Bảng trên đo lại công bằng
cho cả hai mức.

**Chất lượng khi giảm mức suy nghĩ:** ở mức `low`, lần chạy đầu trượt bài dịch cả 2 lượt (22/24): model đổi
"120.000.000" thành "120,000,000" theo kiểu tiếng Anh, vi phạm yêu cầu giữ nguyên số. Cách sửa không dựa vào prompt mà
chặn bằng code: `word_rewrite_paragraphs` đối chiếu mọi số/ngày/tiền giữa bản cũ và bản mới. Nếu có số bị đổi, tool từ
chối ghi và báo lại cho model, trừ khi người dùng yêu cầu đổi số (`allow_number_changes`). Sau đó đạt 24/24. Ở lượt
chạy này model tự giữ đúng số nên chốt kiểm tra chưa phải chặn lần nào; chốt này là lớp bảo vệ khi model sai.

Mức suy nghĩ đổi được bằng `AGENT_THINKING_LEVEL` trong `.env` (`low` | `medium` | `high`; trống = mặc định của model).

## Chi tiết lượt chạy hiện tại

| Yêu cầu | Nhóm | Lượt 1 | Lượt 2 | Bước |
|---|---|---|---|---|
| Tạo bảng 12 tháng + tổng + biểu đồ | Excel | Đạt | Đạt | 3 / 3 |
| Tô đỏ giá trị âm trong vùng chọn | Sửa một phần | Đạt | Đạt | 2 / 2 |
| Thêm dòng Tổng | Excel | Đạt | Đạt | 3 / 3 |
| Sắp xếp theo Q1 giảm dần | Excel | Đạt | Đạt | 3 / 3 |
| Soạn báo cáo 3 đề mục | Word | Đạt | Đạt | 2 / 2 |
| Thay "khách hàng" → "đối tác" | Word | Đạt | Đạt | 2 / 2 |
| Rà soát bằng Track Changes + nhận xét | Rà soát | Đạt | Đạt | 3 / 3 |
| Dịch sang tiếng Anh giữ số, ngày | Dịch | Đạt | Đạt | 3 / 3 |
| 5 slide có ghi chú | PowerPoint | Đạt | Đạt | 6 / 5 |
| In đậm, tô cam từ khoá trên slide | Định dạng từ khoá | Đạt | Đạt | 2 / 4 |
| "Hoàn tác lần sửa vừa rồi" | Hoàn tác | Đạt | Đạt | 2 / 2 |
| "Sửa cái bảng kia đi" (mơ hồ) | Yêu cầu không rõ | Đạt — hỏi lại | Đạt — hỏi lại | 2 / 1 |

## Lỗi bộ đánh giá đã giúp phát hiện và sửa

1. **Rà soát hợp đồng:** nhận xét vào đoạn vừa đề xuất sửa báo "Đoạn trống", và `word_inspect` hiện đoạn có Track
   Changes là chuỗi rỗng, khiến agent tưởng đoạn bị xoá rồi sửa thẳng nội dung. Đã sửa: đọc chữ theo dạng "chấp nhận mọi
   đề xuất", báo `pending_suggestion`, nhận xét được đoạn có Track Changes.
2. **Làm 5 slide:** agent sửa chữ từng shape một, vượt 10 bước. Đã sửa: `pptx_set_text`, `word_suggest_edit`,
   `word_add_comment` nhận nhiều mục một lần.
3. **Độ trễ:** token đầu trung bình 8 s (đo kiểu cũ). Đã chuyển mức suy nghĩ sang `low` và tính token đầu cả với lời
   gọi tool → trung bình 4,3 s.
4. **Dịch đổi định dạng số** ở mức suy nghĩ thấp → thêm chốt kiểm tra giữ nguyên số trong tool.
5. **Bản thân bộ đánh giá:** chạy mỗi yêu cầu trên một event loop riêng (gây lỗi xen kẽ), và cộng dồn nhật ký tool giữa
   các lượt. Cả hai đã sửa.

## Hạn chế

- Mới 12 yêu cầu: cần mở rộng lên khoảng 100 yêu cầu, chạy 3 lượt để số liệu đủ tin cậy cho báo cáo.
- p90 token đầu 9,6 s do dao động phía Gemini. Giao diện đã hiện "Đang xử lý…" ngay khi gửi; có thể bổ sung hiển thị bước
  "Đang lập kế hoạch" để người dùng không phải chờ trong im lặng.
- Máy chạy đánh giá chưa có LibreOffice nên bước tự kiểm tra bố cục slide chỉ trả "chưa cài"; chưa đánh giá OCR (CER)
  vì chưa có bộ ảnh có nhãn.

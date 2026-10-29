# Kết quả đánh giá tự động

Bộ đánh giá: `backend/eval/` — **101 yêu cầu mẫu** trong `cases.json` (13 nhóm), chấm tự động bằng kiểm tra trên tệp
kết quả; **50 ảnh có nhãn** đo đọc ảnh; **15 câu lệnh giọng nói** đo nhận dạng; bộ slide cài lỗi đo tự kiểm tra bố cục.
Chạy lại: xem mục "Đánh giá" trong README. CSV chi tiết lưu ở `backend/eval/results/`.

**Token đầu** = thời gian từ lúc gửi yêu cầu tới phản hồi đầu tiên của model hiện lên giao diện: chữ (thường là dòng
kế hoạch ①→②→③) hoặc bước tool đầu tiên. Cả hai đều hiện ngay cho người dùng.

## Tổng hợp theo chỉ số mục 8.3 của đề xuất — 29/10/2026, Gemini `gemini-3.8-flash`, suy nghĩ `low`

| Chỉ số | Kết quả | Mục tiêu | |
|---|---|---|---|
| Tỉ lệ hoàn thành tác vụ | **92,8%** (90/97) lượt đầu; 97/97 sau khi sửa các lỗi lượt đầu phát hiện | ≥ 85% | ✅ |
| Độ chính xác gọi công cụ | **97,2%** | ≥ 90% | ✅ |
| Tính toàn vẹn tệp | **100%** | 100% | ✅ |
| Thời gian tới token đầu | trung bình 3,4 s · trung vị 2,5 s · p90 6,8 s | < 5 s | ✅ (trung bình) |
| Thời gian hoàn thành | trung bình 17,4 s | tác vụ đơn < 60 s | ✅ |
| Số bước trung bình | 3,5 | ≤ 10 | ✅ |
| Độ chính xác nhận dạng chữ từ ảnh (CER) | **0%** trên 50 ảnh (cả ảnh tối, nghiêng, mờ, nhiễu) | ≤ 5% với ảnh rõ | ✅ |
| Độ chính xác trích xuất bảng | **100%** ô đúng giá trị và vị trí (40 ảnh có bảng) | ≥ 90% | ✅ |
| Tỉ lệ phát hiện lỗi bố cục | **100%** (66 slide cài lỗi), báo nhầm 0% (36 slide sạch) | ≥ 80% | ✅ |
| Nhận dạng giọng nói (đường dự phòng máy chủ) | WER **3,7%**, 77% câu đúng hoàn toàn (30 bản ghi tổng hợp) | — | |
| Độ phủ kiểm thử backend | 86% (`pytest --cov`) | ≥ 70% | ✅ |
| Mức độ dễ dùng (SUS) | chưa có — phiếu `#/sus` sẵn sàng cho buổi thử nghiệm | ≥ 70 | ⏳ |

Lưu ý khi đọc số: ảnh OCR là **ảnh tổng hợp** (chữ in sạch, làm khó bằng tối/nghiêng/mờ/nhiễu), bản ghi giọng nói là
**giọng đọc tổng hợp** (Gemini TTS) → số liệu là mốc ban đầu, cao hơn thực tế. Báo cáo cuối cần thêm ảnh chụp thật
(`backend/eval/ocr_dataset/`, định dạng nhãn trong `labels.json`) và giọng thật của người dùng
(`backend/eval/voice_dataset/recordings/`). 4 yêu cầu phân tích cần sandbox `run_python` bị bỏ qua khi chạy trên máy
không có Docker (97/101 yêu cầu được chạy).

### Theo nhóm (lượt đầu, 97 yêu cầu)

| Nhóm | Số yêu cầu | Đạt | Thời gian TB (s) | Bước TB |
|---|---|---|---|---|
| Excel | 18 | 17 | 20,2 | 3,9 |
| PowerPoint | 13 | 11 | 27,2 | 5,6 |
| Word | 12 | 11 | 13,7 | 2,5 |
| Công thức toán (Word + PowerPoint) | 12 | 11 | 20,8 | 3,4 |
| Sửa một phần (vùng chọn) | 8 | 8 | 8,9 | 2,8 |
| Dịch | 7 | 7 | 15,7 | 4,0 |
| Rà soát | 5 | 5 | 17,6 | 3,0 |
| Yêu cầu không rõ | 5 | 3 | 16,9 | 3,2 |
| Mẫu thiết kế | 5 | 5 | 15,3 | 3,2 |
| Định dạng từ khoá | 4 | 4 | 6,8 | 2,2 |
| Hoàn tác | 4 | 4 | 13,9 | 2,0 |
| Phân tích (không cần sandbox) | 2 | 2 | 8,2 | 2,5 |
| So sánh | 2 | 2 | 11,6 | 2,0 |

### 7 yêu cầu trượt ở lượt đầu và cách xử lý

| Yêu cầu | Nguyên nhân | Xử lý | Chạy lại |
|---|---|---|---|
| xlsx-09 tạo sheet Thống kê | Chưa có tool thêm sheet vào tệp có sẵn; model thử `run_python` (máy không có sandbox) rồi hết 10 bước | Thêm `excel_add_sheet`; tool thiếu dịch vụ (`run_python`, `render_pages`, `ocr_image`) không khai báo cho model | ✅ 6 bước |
| pptx-03, pptx-12 sơ đồ / dòng thời gian | Lặp "sửa → kiểm tra bố cục" nhiều vòng, gọi `render_pages` khi không có LibreOffice → hết 10 bước | Hướng dẫn: kiểm tra một lần, sửa hết trong một lần gọi, hết lỗi thì dừng; ẩn `render_pages` khi không dùng được | ✅ 5 và 8 bước |
| docx-14, math-05 | Đề không nói "Word": model làm bảng Excel / trả lời ngay trong chat (cách hiểu hợp lý) | Sửa đề cho rõ | ✅ |
| vague-02, vague-05 | Có tệp đang mở nên model làm trên tệp đó — đúng quy tắc "không nêu tệp → dùng tệp đang mở" | Đổi thành yêu cầu mơ hồ thật sự ("sửa như tôi dặn hôm qua") | ✅ hỏi lại |

### Nhận dạng giọng nói — lỗi còn lại

Lỗi tập trung ở từ đầu câu và từ tiếng Anh xen lẫn: "Sắp xếp" → "Xếp xếp", "Soạn" → "Xoang", "kiến nghị" → "ký
nghị", "ô B2" → "OB2", "chart" → "chạc", "Hoàn tác" → "Hoàn tất". Giao diện luôn cho xem và sửa bản chép lời trước khi
gửi (không tự gửi). WER đã chuẩn hoá: bỏ dấu câu, "mười hai" ≡ "12", "15 tháng 01 năm 2026" ≡ "15/01/2026".

## Lượt đánh giá trước (12 yêu cầu, tối ưu độ trễ) — 29/10/2026, Gemini `gemini-3.8-flash`, mức suy nghĩ `low`, 2 lượt × 12 yêu cầu

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

# Hệ thống thiết kế giao diện

Cảm hứng thị giác lấy từ hai trang cộng đồng/nhà phát triển mà nhóm tham khảo: giao diện nền tối có điểm nhấn
ấm và thẻ đánh số kiểu tạp chí, cùng phong cách bảng điều khiển cho lập trình viên (khối terminal, nhãn mono,
chuyển sáng/tối). Giao diện của dự án là thiết kế riêng: không dùng logo, tên hay nội dung của các trang đó.
Mã nguồn: `frontend/src/styles.css`.

## Màu

| Token | Đêm (mặc định) | Ngày | Dùng cho |
|---|---|---|---|
| `--bg` | `#0f1923` | `#f6f3ec` | nền trang |
| `--surface` / `--elevated` | `#162232` / `#1e2f42` | `#ffffff` / `#f1ede4` | thẻ, khung, hộp thoại |
| `--border` | `#253549` | `#e2dccf` | viền |
| `--text` / `--text-2` / `--text-3` | `#f0ede6` / `#a3b3c7` / `#7189a6` | `#17222d` / `#4b5a69` / `#6b7987` | chữ chính / phụ / mờ |
| `--coral` | `#ff6b4a` | `#d9472b` | hành động chính, tệp đang chọn, PowerPoint |
| `--amber` | `#ffb830` | `#a86b00` | trả lời của trợ lý, chỗ vừa thay đổi |
| `--sky` | `#38bdf8` | `#0369a1` | vùng chọn, công thức, Word |
| `--mint` | `#34d399` | `#047857` | thành công, Excel |
| `--danger` | `#f87171` | `#b91c1c` | lỗi, thao tác phá huỷ |

Màu nhấn ở chế độ Ngày được làm đậm hơn để chữ trên nền sáng đạt tương phản đọc được. Màu biểu đồ dùng bảng
Okabe–Ito (phân biệt được với người mù màu), giống nhau ở biểu đồ Excel/PowerPoint do trợ lý tạo và biểu đồ SVG xem trước.

## Chữ

| Vai trò | Font | Ở đâu |
|---|---|---|
| Tiêu đề, số lớn | Anybody (variable) | logo, tiêu đề màn hình chào, số thứ tự thẻ, tên tệp |
| Nội dung | Be Vietnam Pro | toàn bộ văn bản |
| Kỹ thuật | JetBrains Mono (variable) | nhật ký tool, địa chỉ ô, công thức, phiên bản |

Font được **tự host** qua `@fontsource` (không gọi Google Fonts): chạy được khi offline và không lộ địa chỉ IP người
dùng — đúng tinh thần "chạy cục bộ" của đề xuất.

## Thành phần

- **Thanh trên cùng:** logo, chọn phiên, Hoàn tác yêu cầu, mô hình AI đang dùng (chấm xanh = đã kết nối), nhãn PII khi
  đang ẩn danh, nút sáng/tối. Nền mờ (backdrop blur).
- **Hội thoại (trái):** tin người dùng là bong bóng viền san hô; trả lời của trợ lý có vạch hổ phách bên trái, dòng kế
  hoạch ①→②→③ tách riêng bằng font mono; các bước tool gom thành **khối terminal** (bấm một dòng để xem tham số/kết
  quả); thay đổi tệp là thẻ hổ phách bấm để mở tệp. Ô soạn bo tròn, sáng viền san hô khi đang nhập.
- **Không gian làm việc (phải):** tab tệp dạng viên thuốc có nhãn loại tệp; xem trước Excel (lưới tự viết, công thức tô
  xanh, ô vừa đổi nền hổ phách, kéo chọn vùng), biểu đồ SVG, dàn ý Word/bản in, ảnh slide. Kéo thả tệp vào vùng này.
- **Màn hình chào:** tiêu đề lớn có dải màu san hô → hổ phách, số liệu nhanh, **thẻ việc mẫu đánh số 01–06** (các kịch
  bản mục 3.3 của đề xuất) — bấm để điền sẵn yêu cầu vào ô soạn; di chuột thì thẻ nổi lên và hiện vạch san hô.

## Khả năng tiếp cận

- Mọi nút biểu tượng có `aria-label`; hộp thoại có `role="dialog"`, `aria-modal`; nhật ký tool có `role="log"`.
- Viền focus `:focus-visible` màu xanh trời trên mọi phần tử tương tác.
- `prefers-reduced-motion`: tắt hiệu ứng chuyển động.
- Màn hình hẹp (< 860 px): xem trước lên trên, hội thoại xuống dưới.
- Việc còn lại (TV4): kiểm tra tương phản đầy đủ, điều hướng lưới Excel bằng bàn phím, thử với trình đọc màn hình.

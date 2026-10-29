# Hệ thống thiết kế giao diện

Kiểu **cửa sổ ứng dụng**: nền xám nhạt, một khung trắng bo góc lớn phủ gần hết màn hình, trên cùng là dải tab như trình
duyệt (Trang chủ + các phiên đang mở). Thẻ trắng không viền, tiêu đề lớn nét mảnh, nút dạng viên thuốc. Xanh biển là
màu hành động, cam là màu nhấn. Bố cục trang chủ theo kiểu Google Sheets/Docs (chọn loại tệp → phiên gần đây có ảnh xem
trước). Đây là thiết kế riêng của dự án: không dùng logo, tên hay nội dung của trang tham khảo.
Mã nguồn: `frontend/src/styles.css`.

## Nguyên tắc

- **Khung cửa sổ:** `.app` cách mép màn hình 12 px, bo 22 px, đổ bóng mềm; rộng hết màn hình (không giới hạn chiều
  rộng). Nội dung trang chủ căn giữa, tối đa 1520 px.
- **Tab liền nội dung:** tab đang xem (`.wtab.on`) cao hơn, cùng màu với vùng `.surface` bên dưới và có góc lượn ngược
  hai bên, nên trông như "dính" vào nội dung. Tab phiên lưu trong trình duyệt (tối đa 6), có nút đóng.
- **Thẻ không viền:** phân lớp bằng nền (`surface` xám nhạt → `card` trắng); viền 1 px chỉ dùng cho ô nhập và nút phụ.
- **Bo tròn:** nút, ô tìm kiếm, bộ lọc, chip là viên thuốc (999 px); thẻ 18 px; hộp thoại 22 px.
- **Không dùng ký tự làm icon:** mọi icon là SVG từ bộ `lucide-react` (logo cũng là SVG); icon loại tệp tô màu theo loại.
- **Nút:** `.primary`/`.solid` tô xanh biển (Gửi, Tải tệp lên, Tải về, Lưu); lựa chọn đang bật (bộ lọc, tab tệp) tô đen.
- **Ảnh minh hoạ:** ô chọn loại tệp dùng nền gạch chéo (`--hatch`) với hình vẽ SVG ở giữa.
- **Thông báo:** toast nền đen ở góc dưới phải.

## Màu

| Token | Sáng (mặc định) | Tối | Dùng cho |
|---|---|---|---|
| `--canvas` | `#e8e9ec` | `#0d0e10` | nền ngoài khung cửa sổ |
| `--frame` / `--surface` / `--card` | `#ffffff` / `#f1f2f4` / `#ffffff` | `#17181b` / `#1e2024` / `#26282d` | khung + thanh tab / vùng nội dung / thẻ |
| `--line` | `#e5e6e9` | `#34373d` | viền ô nhập, kẻ lưới |
| `--ink` / `--ink-2` / `--muted` | `#111214` / `#3b3f46` / `#6f747d` | `#f2f3f5` / `#c9ccd2` / `#949aa3` | chữ chính / phụ / mờ; lựa chọn đang bật |
| `--blue` | `#1d5fe0` | `#5b8ff2` | hành động chính, tin người dùng, kế hoạch, vùng chọn, Word |
| `--orange` | `#ef5a17` | `#ff7b3d` | nhấn, chỗ vừa thay đổi, PowerPoint |
| `--green` | `#14894a` | `#3cc47a` | thành công, đã kết nối, Excel |
| `--red` | `#d92d20` | `#ff6b5e` | lỗi, thao tác phá huỷ |

Biểu đồ dùng bảng Okabe–Ito (phân biệt được với người mù màu), giống nhau ở biểu đồ Excel/PowerPoint do trợ lý tạo và
biểu đồ SVG xem trước.

## Chữ

| Vai trò | Font | Ở đâu |
|---|---|---|
| Toàn bộ giao diện | Inter Tight (variable, 100–900) | tiêu đề lớn nét 300, nhãn/nút 500, nội dung 400 |
| Kỹ thuật | monospace hệ thống | nhật ký tool, địa chỉ ô, công thức, mã `run_python` |

Font được **tự host** qua `@fontsource-variable/inter-tight` (không gọi Google Fonts): chạy được khi offline, không lộ
địa chỉ IP người dùng và có đủ dấu tiếng Việt.

## Màn hình

Hai màn hình, định tuyến bằng hash (`#/` và `#/s/<id>`), dùng chung thanh cửa sổ: logo, dải tab, phần riêng của trang
(ô tìm kiếm ở trang chủ; tên phiên + Hoàn tác yêu cầu ở không gian làm việc), mô hình AI đang dùng (chấm xanh = đã kết
nối, nhãn PII khi đang ẩn danh), nút sáng/tối.

**Trang chủ** (giống trang chủ Google Sheets/Docs):
- Đầu trang: dòng phụ nhỏ + tiêu đề lớn **Bắt đầu làm việc mới**; bốn ô chọn — Bảng tính (Excel), Tài liệu (Word), Bản
  trình chiếu (PowerPoint), Mở tệp có sẵn. Chọn loại nào thì tạo phiên mới kèm tệp trống loại đó rồi mở phiên.
- **Phiên làm việc gần đây**: lưới thẻ có **ảnh xem trước nội dung thật** của tệp vừa sửa gần nhất (bảng ô kèm giá trị,
  trang chữ, slide đầu), tên phiên, loại tệp, thời điểm sửa, số tệp và số yêu cầu. Lọc theo loại (viên thuốc, đang bật
  tô đen), tìm theo tên phiên/tệp, sắp xếp; xoá phiên phải xác nhận.

**Không gian làm việc** (chỉ mở khi đã chọn loại hoặc phiên; phiên tự thành tab):
- **Hội thoại (thẻ trái):** tin người dùng là bong bóng xanh biển; trả lời của trợ lý hiển thị Markdown; dòng kế hoạch
  ①→②→③ là ô nền xanh nhạt; các bước tool gom thành **khối terminal** nền đen (bấm một dòng để xem tham số/kết quả);
  thay đổi tệp là thẻ bấm để mở tệp.
- **Tệp và xem trước (thẻ phải):** tab tệp (tệp đang mở tô đen); lưới Excel có **thanh công thức** (ô hiện kết quả,
  công thức gốc hiện ở thanh trên), ô vừa đổi nền cam nhạt, bấm một ô để đặt vị trí bắt đầu, kéo nhiều ô để giới hạn
  vùng sửa; biểu đồ SVG, dàn ý Word/bản in, ảnh slide. Kéo thả tệp để tải lên.
- **Hộp thoại:** thẻ trắng bo 22 px trên lớp phủ mờ; lựa chọn nhà cung cấp đang bật viền xanh.

## Khả năng tiếp cận

- Mọi nút biểu tượng có `aria-label`; hộp thoại có `role="dialog"`, `aria-modal`; nhật ký tool có `role="log"`.
- Viền focus `:focus-visible` màu xanh biển trên mọi phần tử tương tác.
- `prefers-reduced-motion`: tắt hiệu ứng chuyển động.
- Màn hình hẹp (< 860 px): khung cửa sổ bỏ lề và bo góc, xem trước lên trên, hội thoại xuống dưới.
- Việc còn lại (TV4): đo tương phản đầy đủ, điều hướng lưới Excel bằng bàn phím, thử với trình đọc màn hình.

# Hệ thống thiết kế giao diện

Phong cách vuông vức, lấy cảm hứng từ trang cộng đồng vibe coding mà nhóm tham khảo: **không bo góc**, viền 1px,
nền xanh đêm, nhấn san hô/hổ phách/xanh trời, font Anybody cho tiêu đề. Bố cục trang chủ theo kiểu Google Sheets/Docs
(chọn loại tệp → danh sách phiên gần đây có ảnh xem trước). Thêm vài chi tiết kiểu bảng điều khiển cho lập trình viên
(khối terminal cho các bước tool, nền lưới chấm, chuyển sáng/tối). Đây là thiết kế riêng của dự án: không dùng logo,
tên hay nội dung của các trang tham khảo.
Mã nguồn: `frontend/src/styles.css`.

## Nguyên tắc

- **Vuông:** mọi khung, nút, nhãn, hộp thoại đều không bo góc (chỉ chấm trạng thái là tròn).
- **Không dùng ký tự làm icon:** mọi icon là SVG từ bộ `lucide-react` (logo cũng là SVG); icon loại tệp tô màu theo loại.
- **Viền thay bóng:** phân lớp bằng viền 1px và nền `surface`/`elevated`; bóng chỉ dùng khi di chuột vào thẻ.
- **Vạch nhấn 4px bên trái** cho thứ cần chú ý: đoạn giới thiệu, trả lời của trợ lý, thẻ đang di chuột, thay đổi tệp,
  lựa chọn đang bật, phiên bản hiện tại.
- **Nút:** chữ Anybody giãn nhẹ. Nút nhấn mạnh (`.primary`) viền san hô + nền san hô nhạt → di chuột thì tô đặc;
  nút chính nhất (`.solid`: Gửi, Tải tệp lên, Lưu) tô đặc sẵn.

## Màu

| Token | Đêm (mặc định) | Ngày | Dùng cho |
|---|---|---|---|
| `--bg` | `#0f1923` | `#f4f1ea` | nền trang |
| `--surface` / `--elevated` | `#162232` / `#1e2f42` | `#ffffff` / `#ece7dc` | khung, thẻ, nút, hộp thoại |
| `--border` | `#253549` | `#d8d0bf` | viền |
| `--text` / `--text-2` / `--text-3` | `#f0ede6` / `#8b9db5` / `#6a82a1` | `#15202b` / `#4b5a69` / `#66727f` | chữ chính / phụ / mờ |
| `--coral` | `#ff6b4a` | `#d9472b` | hành động chính, tệp đang chọn, PowerPoint |
| `--amber` | `#ffb830` | `#9a6200` | trả lời của trợ lý, chỗ vừa thay đổi, số thứ tự thẻ |
| `--sky` | `#38bdf8` | `#0369a1` | vùng chọn, công thức, Word |
| `--mint` | `#34d399` | `#047857` | thành công, Excel |
| `--danger` | `#f87171` | `#b91c1c` | lỗi, thao tác phá huỷ |

Màu nhấn ở chế độ Ngày được làm đậm hơn để chữ trên nền sáng đọc được. Biểu đồ dùng bảng Okabe–Ito (phân biệt được
với người mù màu), giống nhau ở biểu đồ Excel/PowerPoint do trợ lý tạo và biểu đồ SVG xem trước.

## Chữ

| Vai trò | Font | Ở đâu |
|---|---|---|
| Tiêu đề, nút, nhãn | Anybody (variable) | logo, tiêu đề mục, nút, tab, tên phiên, tên tệp |
| Nội dung | Be Vietnam Pro | đoạn văn, tin nhắn, mô tả |
| Kỹ thuật | monospace hệ thống | nhật ký tool, địa chỉ ô, công thức, mã `run_python` |

Font được **tự host** qua `@fontsource` (không gọi Google Fonts): chạy được khi offline và không lộ địa chỉ IP người
dùng — đúng tinh thần "chạy cục bộ" của đề xuất.

## Màn hình

Hai màn hình, định tuyến bằng hash (`#/` và `#/s/<id>`):

**Trang chủ** (giống trang chủ Google Sheets/Docs):
- Dải **Bắt đầu làm việc mới**: bốn ô chọn — Bảng tính (Excel), Tài liệu (Word), Bản trình chiếu (PowerPoint), Mở tệp có
  sẵn. Chọn loại nào thì tạo phiên mới kèm tệp trống loại đó rồi mở không gian làm việc.
- **Phiên làm việc gần đây**: lưới thẻ có **ảnh xem trước nội dung thật** của tệp vừa sửa gần nhất trong phiên (bảng ô
  kèm giá trị, trang chữ, slide đầu), tên phiên, loại tệp, thời điểm sửa, số tệp và số yêu cầu. Lọc theo loại, tìm theo
  tên phiên/tệp, sắp xếp theo thời gian hoặc tên; xoá phiên phải xác nhận.

**Không gian làm việc** (chỉ mở khi đã chọn loại hoặc phiên):
- **Thanh trên cùng:** nút về trang chủ, logo, tên phiên (bấm để đổi tên), Hoàn tác yêu cầu, mô hình AI đang dùng (chấm
  xanh = đã kết nối), nhãn PII khi đang ẩn danh, nút sáng/tối.
- **Hội thoại (trái):** tin người dùng là khung viền san hô; trả lời của trợ lý có vạch hổ phách; dòng kế hoạch ①→②→③ in
  đậm màu hổ phách; các bước tool gom thành **khối terminal** (bấm một dòng để xem tham số/kết quả); thay đổi tệp là thẻ
  vạch hổ phách, bấm để mở tệp.
- **Tệp và xem trước (phải, nền lưới chấm):** tab tệp (tệp đang mở tô đặc san hô), lưới Excel tối thiểu 30×8 (công thức
  màu xanh trời, ô vừa đổi nền hổ phách, kéo chọn vùng), biểu đồ SVG, dàn ý Word/bản in, ảnh slide. Kéo thả tệp để tải lên.
- **Hộp thoại:** vạch san hô phía trên; lựa chọn nhà cung cấp đang bật có vạch trái.

## Khả năng tiếp cận

- Mọi nút biểu tượng có `aria-label`; hộp thoại có `role="dialog"`, `aria-modal`; nhật ký tool có `role="log"`.
- Viền focus `:focus-visible` màu xanh trời trên mọi phần tử tương tác.
- `prefers-reduced-motion`: tắt hiệu ứng chuyển động.
- Màn hình hẹp (< 860 px): xem trước lên trên, hội thoại xuống dưới.
- Việc còn lại (TV4): đo tương phản đầy đủ, điều hướng lưới Excel bằng bàn phím, thử với trình đọc màn hình.

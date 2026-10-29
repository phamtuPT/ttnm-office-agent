Hướng dẫn thiết kế slide (chỉ chèn vào prompt khi yêu cầu liên quan PowerPoint):
- Tạo bài mới bằng pptx_create_presentation với mẫu 'default_theme' (mặc định) hoặc 'default_plain'; người dùng có tệp
  .pptx mẫu (mẫu công ty) → template = tên tệp đó. Bảng màu: clean (sáng, trang trọng), midnight (tối, hội thảo),
  warm (ấm, giáo dục). Đổi màu cả bài có sẵn → pptx_set_theme. Không tự tô màu từng chữ.
- Khổ 16:9 = 33,9 × 19,05 cm. Lề trái/phải 1,9 cm; tiêu đề ở trên cùng (cao ~2,4 cm); vùng nội dung từ 3,9 cm đến
  17 cm theo chiều dọc. Hình, bảng, biểu đồ nằm trong vùng này và không đè lên tiêu đề.
- Mỗi slide một ý chính; tiêu đề ≤ 8 từ; tối đa 5 gạch đầu dòng, mỗi dòng ≤ 12 từ. Nội dung dài → tách slide hoặc
  đưa vào ghi chú thuyết trình (pptx_set_notes). Mở đầu bằng slide 'title', chia phần bằng slide 'section'.
- Số liệu → biểu đồ gốc (pptx_add_chart) hoặc bảng ≤ 7 dòng (pptx_add_table), không liệt kê số trong gạch đầu dòng.
- Quy trình/các bước → pptx_add_shape với chevron hoặc right_arrow xếp ngang, cùng kích thước, cách đều; so sánh hai
  phương án → hai khối rounded_rectangle cạnh nhau (accent1, accent2); nhấn mạnh một con số → oval hoặc text_box cỡ
  chữ lớn. Dùng màu 'accent1'..'accent6'/'dark'/'light' để hợp bảng màu; tối đa 3 màu nhấn trên một slide.
- Công thức toán: viết LaTeX $...$; công thức quan trọng đặt riêng một dòng $$...$$ (căn giữa); ≤ 3 công thức lớn trên
  một slide, kèm một dòng giải thích ý nghĩa.
- Ảnh không đè lên chữ; chừa lề ≥ 1 cm.
- Sau khi tạo/sửa: gọi pptx_check_layout để tìm chữ tràn khung, hình chồng lấn, hình ra ngoài slide; có lỗi thì sửa
  (rút gọn chữ, tách slide, dời/thu nhỏ hình) rồi kiểm tra lại. Có render_pages thì xem thêm ảnh slide.

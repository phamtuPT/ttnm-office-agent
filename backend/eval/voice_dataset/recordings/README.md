# Bản ghi giọng nói thật

Đặt bản ghi của từng người đọc vào thư mục này, tên tệp `<id câu>-<người đọc>.<đuôi>`, ví dụ `v01-minh.webm`,
`v07-tu.wav`. `id` lấy từ `../commands.json`. Đuôi hỗ trợ: .wav, .webm, .mp3, .m4a, .ogg.

Gợi ý thu: điện thoại hoặc micro laptop, phòng bình thường (có tiếng ồn nhẹ cũng được), đọc tự nhiên như khi ra lệnh.
Sau đó chạy `python -m eval.voice_eval run` để tính WER/CER cho cả bản ghi thật và bản tổng hợp.

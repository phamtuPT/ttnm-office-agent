# Office AI Agent — Trợ lý AI tạo lập và chỉnh sửa tài liệu Office đa phương thức

Bài tập lớn môn Tương tác người máy. Người dùng giao việc bằng **chữ, giọng nói hoặc ảnh**; trợ lý lập kế
hoạch rồi trực tiếp **tạo hoặc sửa tệp Word, Excel, PowerPoint thật**, xem trước ngay trên trình duyệt. Mọi
thay đổi được sao lưu, xem được khác biệt và **hoàn tác một nhấp**. Chạy được với Gemini, OpenAI hoặc
Ollama (cục bộ — dữ liệu không rời máy).

- Đề xuất: [docs/đề-xuất-btl.docx](docs/đề-xuất-btl.docx) · Phân công: [docs/PHAN_CONG.md](docs/PHAN_CONG.md)
- Kiến trúc và đối chiếu với đề xuất: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- API REST + WebSocket: [docs/API.md](docs/API.md) · Cơ sở dữ liệu: [docs/DATABASE.md](docs/DATABASE.md)
- Mô hình AI, chi phí, lưu ý: [docs/LLM.md](docs/LLM.md) · Kết quả đánh giá: [docs/EVAL.md](docs/EVAL.md) · Hệ thống thiết kế giao diện: [docs/DESIGN.md](docs/DESIGN.md)

## Tính năng chính

- **Excel:** bảng, công thức (kiểm tra #NAME?/#REF! trước khi ghi), định dạng, tô màu có điều kiện, biểu đồ gốc,
  sắp xếp, lọc. Lưới xem trước hiện kết quả công thức + thanh công thức, dùng được bằng bàn phím và **sửa ô trực tiếp**.
- **Word:** soạn tài liệu, sửa/chèn đoạn, bảng, ảnh, tìm-thay, Track Changes, nhận xét, dịch giữ số liệu,
  **sao chép phong cách** từ tài liệu mẫu.
- **Công thức toán** trong Word và PowerPoint: trợ lý viết LaTeX `$...$`, hệ thống chuyển thành công thức Office
  thật (sửa được trong Word/PowerPoint); đọc lại công thức có sẵn; hiển thị bằng KaTeX trong chat và khung xem trước.
- **PowerPoint:** tạo từ **mẫu thiết kế** 16:9 (hoặc mẫu .pptx của người dùng), 3 bảng màu, hình khối/sơ đồ, bảng,
  biểu đồ gốc, ghi chú; **tự kiểm tra bố cục** (chữ tràn, chồng lấn, ra ngoài slide) không cần LibreOffice.
- **Đa phương thức:** gõ, nói (Web Speech API + dự phòng máy chủ), gửi ảnh (đọc hoá đơn/bảng thành Excel/Word).
- **An toàn:** ghi nguyên tử, 20 thế hệ sao lưu, xem khác biệt, hoàn tác theo yêu cầu; che PII trước khi gửi lên đám mây.
- **Nhiều người dùng (tuỳ chọn):** `AUTH_ENABLED=true` → đăng nhập, mỗi người chỉ thấy phiên của mình.
- **Đánh giá:** 101 yêu cầu mẫu, 50 ảnh đo OCR, 15 câu lệnh giọng nói, phiếu SUS trong ứng dụng (`#/sus`).

## Cấu trúc

```
backend/    FastAPI + agent + công cụ Office (Python 3.12), eval/ bộ đánh giá
frontend/   React 18 + TypeScript + Vite
sandbox/    Dịch vụ chạy mã phân tích dữ liệu (run_python), cách ly, không có mạng
docs/       Đề xuất, phân công, tài liệu thiết kế
```

## Chạy bằng Docker (demo)

```bash
cp .env.example .env            # điền GEMINI_API_KEY (hoặc nhập sau trên giao diện) và POSTGRES_PASSWORD
docker compose up --build       # http://localhost:3000 (kèm PostgreSQL)
```

Thêm Ollama chạy trên máy: `docker compose --profile ollama up --build`, đặt `OLLAMA_BASE_URL=http://ollama:11434/v1`
rồi tải model: `docker compose exec ollama ollama pull <tên model>`.

## Chạy khi phát triển

Yêu cầu: Python 3.12, Node 24. Tuỳ chọn: LibreOffice (để xem ảnh slide và để agent tự kiểm tra bố cục).

**Backend**

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example .env
python scripts/dev_postgres.py  # PostgreSQL tại chỗ, không cần Docker (hoặc: docker compose up -d db)
uvicorn app.main:app --reload --port 8000
```

CSDL: xem [docs/DATABASE.md](docs/DATABASE.md) (migration, chuyển dữ liệu từ SQLite cũ, test trên Postgres).

Chưa có API key? Để `LLM_PROVIDER=mock` — trợ lý giả trả lời để làm giao diện (gõ “tạo bảng”, “hoàn tác”).
Đổi nhà cung cấp/model/khoá API ngay trên giao diện bằng nút ⚙.

**Frontend**

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Backend chạy cổng khác: `BACKEND_URL=http://localhost:8010 npm run dev`.

**Kiểm thử**

```bash
cd backend && python -m pytest --cov=app
cd backend && TEST_DATABASE_URL=postgresql://office@localhost:5432/postgres python -m pytest   # trên Postgres
cd frontend && npm test && npm run build
cd frontend && npm run e2e      # Playwright: tự chạy backend (trợ lý giả, SQLite tạm) + Vite, dùng Edge/Chrome có sẵn
```

**Đánh giá theo mục 8 của đề xuất** (chạy bộ yêu cầu mẫu, xuất CSV + tóm tắt chỉ số vào `backend/eval/results/`)

```bash
cd backend && python -m eval.run_eval --provider gemini --repeat 3     # 101 yêu cầu (--group "Công thức toán" để chạy một nhóm)
cd backend && python -m eval.ocr_eval run --provider gemini           # 50 ảnh có nhãn → CER, độ chính xác trích bảng
cd backend && python -m eval.voice_eval synth && python -m eval.voice_eval run   # 15 câu lệnh giọng nói → WER
cd backend && python -m eval.layout_eval                              # tỉ lệ phát hiện lỗi bố cục slide
```

Phiếu SUS cho buổi thử nghiệm với người dùng: mở `http://localhost:5173/#/sus`, kết quả ở `#/sus/ket-qua`.

## Quy ước

- Không commit `.env`, `storage/`, tệp người dùng thật.
- Đổi schema DB → sửa `backend/app/db.py` rồi `alembic revision --autogenerate` (xem docs/DATABASE.md).
- Thêm tool mới: xem `backend/app/tools/registry.py` và mục của Lê Trọng Thức trong `docs/PHAN_CONG.md`.
- Mỗi tính năng làm trên nhánh riêng, mở Pull Request để người khác xem.

## Giấy phép

Apache 2.0 — xem [LICENSE](LICENSE).

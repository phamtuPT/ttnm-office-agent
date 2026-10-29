# Office AI Agent — Trợ lý AI tạo lập và chỉnh sửa tài liệu Office đa phương thức

Bài tập lớn môn Tương tác người máy. Người dùng giao việc bằng **chữ, giọng nói hoặc ảnh**; trợ lý lập kế
hoạch rồi trực tiếp **tạo hoặc sửa tệp Word, Excel, PowerPoint thật**, xem trước ngay trên trình duyệt. Mọi
thay đổi được sao lưu, xem được khác biệt và **hoàn tác một nhấp**. Chạy được với Gemini, OpenAI hoặc
Ollama (cục bộ — dữ liệu không rời máy).

- Đề xuất: [docs/đề-xuất-btl.docx](docs/đề-xuất-btl.docx) · Phân công: [docs/PHAN_CONG.md](docs/PHAN_CONG.md)
- Kiến trúc và đối chiếu với đề xuất: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- API REST + WebSocket: [docs/API.md](docs/API.md) · Cơ sở dữ liệu: [docs/DATABASE.md](docs/DATABASE.md)
- Mô hình AI, chi phí, lưu ý: [docs/LLM.md](docs/LLM.md) · Kết quả đánh giá: [docs/EVAL.md](docs/EVAL.md) · Hệ thống thiết kế giao diện: [docs/DESIGN.md](docs/DESIGN.md)

## Cấu trúc

```
backend/    FastAPI + agent + công cụ Office (Python 3.12), eval/ bộ đánh giá
frontend/   React 18 + TypeScript + Vite
sandbox/    Dịch vụ chạy mã phân tích dữ liệu (run_python), cách ly, không có mạng
docs/       Đề xuất, phân công, tài liệu thiết kế
```

## Chạy bằng Docker (demo)

```bash
cp .env.example .env            # điền GEMINI_API_KEY (hoặc nhập sau trên giao diện)
docker compose up --build       # http://localhost:3000
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
uvicorn app.main:app --reload --port 8000
```

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
cd frontend && npm test && npm run build
```

**Đánh giá theo mục 8 của đề xuất** (chạy bộ yêu cầu mẫu, xuất CSV + tóm tắt chỉ số vào `backend/eval/results/`)

```bash
cd backend && python -m eval.run_eval --provider gemini --repeat 3
```

## Quy ước

- Không commit `.env`, `storage/`, tệp người dùng thật.
- Đổi schema DB khi phát triển → xoá `backend/storage/app.db` (chưa dùng migration).
- Thêm tool mới: xem `backend/app/tools/registry.py` và mục của Lê Trọng Thức trong `docs/PHAN_CONG.md`.
- Mỗi tính năng làm trên nhánh riêng, mở Pull Request để người khác xem.

## Giấy phép

Apache 2.0 — xem [LICENSE](LICENSE).

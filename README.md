# Trợ lý Office — Đồ án Tương tác người máy

Trợ lý AI dạng chat giúp chỉnh sửa tệp **Excel, Word, PowerPoint** bằng chữ, ảnh hoặc giọng nói.
Agent dùng **Gemini** gọi công cụ để sửa tệp. Người dùng xem trước, chọn vùng được phép sửa, thấy chỗ
thay đổi và **hoàn tác** bất cứ lúc nào.

- Kiến trúc: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- API REST + WebSocket: [docs/API.md](docs/API.md)
- Cơ sở dữ liệu: [docs/DATABASE.md](docs/DATABASE.md)
- Gemini, chi phí, lưu ý: [docs/LLM_GEMINI.md](docs/LLM_GEMINI.md)
- Phân công và việc của từng người: [docs/PHAN_CONG.md](docs/PHAN_CONG.md)

## Cấu trúc

```
backend/    FastAPI + agent Gemini + công cụ Office (Python 3.12)
frontend/   React + Vite + TypeScript
docs/       Tài liệu thiết kế, phân công
```

## Chạy khi phát triển

Yêu cầu: Python 3.12, Node 24.

**Backend**

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example .env         # điền GEMINI_API_KEY, đặt LLM_PROVIDER=gemini
uvicorn app.main:app --reload --port 8000
```

Chưa có API key? Để `LLM_PROVIDER=mock` — trợ lý giả sẽ trả lời để làm giao diện.

**Frontend**

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Backend chạy cổng khác: `BACKEND_URL=http://localhost:8010 npm run dev`.

**Kiểm thử**

```bash
cd backend && python -m pytest -q
cd frontend && npm run build
```

## Chạy bằng Docker

```bash
cp .env.example .env            # điền GEMINI_API_KEY
docker compose up --build       # http://localhost:8080
```

## Quy ước

- Không commit `.env`, `storage/`, tệp người dùng thật.
- Thêm tool mới: xem mẫu trong `backend/app/tools/excel.py` và mục TV2 trong `docs/PHAN_CONG.md`.
- Mỗi tính năng làm trên nhánh riêng, mở Pull Request để người khác xem.

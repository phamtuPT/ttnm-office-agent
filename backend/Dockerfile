FROM python:3.12-slim

# LibreOffice headless: render trang/slide thành ảnh (xem trước + agent tự kiểm tra bố cục).
# Font Noto/DejaVu để hiển thị đúng tiếng Việt.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer libreoffice-impress libreoffice-calc \
       fonts-noto-core fonts-dejavu fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
ENV STORAGE_DIR=/data DATABASE_URL=sqlite:////data/app.db
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.12-slim

RUN pip install --no-cache-dir fastapi==0.162.0 "uvicorn[standard]==0.54.0" \
    pandas numpy scipy statsmodels seaborn matplotlib openpyxl python-docx python-pptx \
    && useradd --create-home --uid 10001 runner

WORKDIR /srv
COPY app.py .
USER runner
EXPOSE 9000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]

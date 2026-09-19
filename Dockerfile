# 1. Gunakan patch minor Python 3.11 terbaru dan pin base image
FROM python:3.11-slim-bookworm

# 2. Set environment variables untuk Python & Security
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# 3. Upgrade OS packages untuk menambal CVE bawaan Debian & install Tesseract + Poppler
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ind \
        poppler-utils && \
    rm -rf /var/lib/apt/lists/*

# 4. Install dependensi Python (manfaatkan Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copy source code
COPY . .

# 6. Jalankan aplikasi sebagai Non-Root User (Prinsip Least Privilege)
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# 7. Start Command
CMD ["sh", "-c", "gunicorn app:app --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT}"]
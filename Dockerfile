FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install Tesseract OCR, data Bahasa Indonesia, & Poppler Utils
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ind \
        poppler-utils && \
    rm -rf /var/lib/apt/lists/*

# Install dependensi Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Buat Non-root User demi keamanan container
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Run via Gunicorn (2 Workers, 2 Threads)
CMD ["gunicorn", "app:app", "--workers", "2", "--threads", "2", "--timeout", "120", "--bind", "0.0.0.0:8080"]
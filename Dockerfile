FROM python:3.11-slim-bookworm

# Mencegah Tesseract menyedot seluruh CPU core secara unthrottled
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_THREAD_LIMIT=1

WORKDIR /app

# Install System Dependencies (Tesseract, Poppler, & OpenCV C-Libraries)
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ind \
        poppler-utils \
        libgl1-mesa-glx \
        libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["gunicorn", "app:app", "--workers", "2", "--threads", "2", "--timeout", "120", "--bind", "0.0.0.0:8080"]
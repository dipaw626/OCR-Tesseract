# Gunakan Python 3.12 Slim terbaru (Versi Python Stable Terbaru)
FROM python:3.12-slim

# Prevent Python & Tesseract dari buffering & CPU unthrottled
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_THREAD_LIMIT=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Upgrade seluruh OS packages ke versi teranyar & install C++ libs
RUN apt-get update && \
    apt-get dist-upgrade -y && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ind \
        poppler-utils \
        libgl1 \
        libglib2.0-0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install & Upgrade Pip serta Requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy seluruh source code
COPY . .

# Konfigurasi Non-Root User untuk keamanan
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["gunicorn", "app:app", "--workers", "2", "--threads", "2", "--timeout", "120", "--access-logfile", "-", "--bind", "0.0.0.0:8080"]
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install Poppler & OpenCV System Dependencies
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        poppler-utils \
        libgl1-mesa-glx \
        libglib2.0-0 \
        g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Gunakan 1 worker & 2 threads agar RAM tetap hemat (~350MB-450MB)
CMD ["gunicorn", "app:app", "--workers", "1", "--threads", "2", "--timeout", "180", "--bind", "0.0.0.0:8080"]
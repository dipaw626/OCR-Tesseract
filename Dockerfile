FROM python:3.11-slim

# 1. Install Tesseract OCR, data bahasa Indonesia, dan Poppler (untuk pdf2image)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ind \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install dependensi Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy seluruh source code
COPY . .

# 4. Expose port dan jalankan Gunicorn
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "gunicorn app:app --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT"]
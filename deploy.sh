#!/bin/bash
echo "Rebuilding OCR Container..."
docker stop ocr_service 2>/dev/null || true
docker rm ocr_service 2>/dev/null || true
docker build -t ocr-engine-v2 .
docker run -d --name ocr_service --restart unless-stopped -p 8080:8080 ocr-engine-v2
echo "Done! Watching live logs..."
docker logs -f ocr_service
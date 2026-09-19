from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes
import os
import sys

app = Flask(__name__)

# Set path tesseract secara eksplisit jika di Linux/Railway
possible_paths = [
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/root/.nix-profile/bin/tesseract"
]

for path in possible_paths:
    if os.path.exists(path):
        pytesseract.pytesseract.tesseract_cmd = path
        break

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Tesseract OCR Service Active"})

@app.route("/ocr", methods=["POST"])
def process_ocr():
    print("--> Received OCR Request from client", file=sys.stderr, flush=True)
    
    try:
        if "file" not in request.files:
            print("--> Error: No file uploaded", file=sys.stderr, flush=True)
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        pdf_bytes = file.read()
        print(f"--> File Size: {len(pdf_bytes)} bytes", file=sys.stderr, flush=True)

        images = convert_from_bytes(pdf_bytes)
        print(f"--> Total Pages: {len(images)}", file=sys.stderr, flush=True)

        full_text = []
        for i, image in enumerate(images):
            # Fallback ke eng jika bahasa ind belum terpasang sempurna
            try:
                text = pytesseract.image_to_string(image, lang="ind+eng")
            except Exception:
                text = pytesseract.image_to_string(image, lang="eng")
                
            full_text.append(f"--- [HALAMAN {i+1}] ---\n{text}")

        print("--> OCR Completed Successfully", file=sys.stderr, flush=True)

        return jsonify({
            "success": True,
            "total_pages": len(images),
            "text": "\n\n".join(full_text)
        })

    except Exception as e:
        print(f"--> OCR Error: {str(e)}", file=sys.stderr, flush=True)
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
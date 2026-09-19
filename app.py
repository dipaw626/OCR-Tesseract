from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes
import os
import shutil
import sys

app = Flask(__name__)

# 1. Cari binary tesseract secara otomatis di sistem
tesseract_bin = shutil.which("tesseract")

if not tesseract_bin:
    # Path cadangan jika tidak terdaftar di $PATH Nixpacks
    fallback_paths = [
        "/root/.nix-profile/bin/tesseract",
        "/nix/var/nix/profiles/default/bin/tesseract",
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract"
    ]
    for path in fallback_paths:
        if os.path.exists(path):
            tesseract_bin = path
            break

if tesseract_bin:
    pytesseract.pytesseract.tesseract_cmd = tesseract_bin
    print(f"--> Tesseract binary set to: {tesseract_bin}", file=sys.stderr, flush=True)
else:
    print("--> WARNING: Tesseract binary NOT found in system!", file=sys.stderr, flush=True)

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "Tesseract OCR Service Active",
        "tesseract_path": pytesseract.pytesseract.tesseract_cmd
    })

@app.route("/ocr", methods=["POST"])
def process_ocr():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file = request.files["file"]
        pdf_bytes = file.read()

        # Ekstraksi halaman PDF ke Image
        images = convert_from_bytes(pdf_bytes)

        full_text = []
        for i, image in enumerate(images):
            # Try ind+eng first, fallback to eng if ind language pack missing
            try:
                text = pytesseract.image_to_string(image, lang="ind+eng")
            except Exception:
                text = pytesseract.image_to_string(image, lang="eng")
                
            full_text.append(f"--- [HALAMAN {i+1}] ---\n{text}")

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
from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes
import os
import shutil
import glob
import sys

app = Flask(__name__)

def find_tesseract():
    # 1. Cek PATH standar
    bin_path = shutil.which("tesseract")
    if bin_path:
        return bin_path
        
    # 2. Cek Nix Profile & Nix Store (Railway Nixpacks)
    possible_paths = [
        "/root/.nix-profile/bin/tesseract",
        "/nix/var/nix/profiles/default/bin/tesseract",
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
            
    # 3. Wildcard search di Nix Store jika terpasang tapi tidak di-link ke PATH
    nix_store_matches = glob.glob("/nix/store/*-tesseract-*/bin/tesseract")
    if nix_store_matches:
        return nix_store_matches[0]
        
    return None

@app.route("/", methods=["GET"])
def home():
    t_path = find_tesseract()
    return jsonify({
        "status": "Tesseract OCR Service Active",
        "tesseract_found": t_path is not None,
        "tesseract_path": t_path
    })

@app.route("/ocr", methods=["POST"])
def process_ocr():
    # KUNCI FIX: Set path tesseract langsung tepat sebelum dipanggil
    t_path = find_tesseract()
    if not t_path:
        return jsonify({
            "success": False, 
            "error": "Tesseract binary tidak ditemukan di server container Nixpacks."
        }), 500
        
    pytesseract.pytesseract.tesseract_cmd = t_path

    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file = request.files["file"]
        pdf_bytes = file.read()

        images = convert_from_bytes(pdf_bytes)

        full_text = []
        for i, image in enumerate(images):
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
from flask import Flask, request, jsonify
import easyocr
from pdf2image import convert_from_bytes
import docx
import io
import numpy as np
from PIL import Image
import sys
import gc

app = Flask(__name__)

# Variabel global untuk menyimpan model
reader = None

def get_reader():
    global reader
    if reader is None:
        # Load model secara on-demand saat ada request masuk
        # Disable model quant/detection berat jika tidak perlu
        reader = easyocr.Reader(['id', 'en'], gpu=False)
    return reader

def extract_from_pdf(pdf_bytes):
    ocr = get_reader()
    images = convert_from_bytes(pdf_bytes, dpi=150) # Kurangi DPI ke 150 agar hemat RAM!
    full_text = []
    
    for i, image in enumerate(images):
        image_np = np.array(image)
        lines = ocr.readtext(image_np, detail=0)
        full_text.append(f"--- [HALAMAN {i+1}] ---\n" + "\n".join(lines))
        
        # Free memory tiap halaman
        del image_np
        gc.collect()
        
    return "\n\n".join(full_text), len(images)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "EasyOCR Multi-Format Service Active"})

@app.route("/ocr", methods=["POST"])
def process_ocr():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file = request.files["file"]
        filename = file.filename.lower()
        file_bytes = file.read()

        if filename.endswith(".pdf"):
            extracted_text, total_pages = extract_from_pdf(file_bytes)
        elif filename.endswith((".png", ".jpg", ".jpeg")):
            ocr = get_reader()
            image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            lines = ocr.readtext(np.array(image), detail=0)
            extracted_text = "\n".join(lines)
            total_pages = 1
        elif filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file_bytes))
            extracted_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            total_pages = 1
        else:
            return jsonify({"success": False, "error": "Format file tidak didukung"}), 400

        # Panggil Garbage Collector untuk melepas RAM
        gc.collect()

        return jsonify({
            "success": True,
            "total_pages": total_pages,
            "text": extracted_text
        })

    except Exception as e:
        print(f"--> OCR Error: {str(e)}", file=sys.stderr, flush=True)
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
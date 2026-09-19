from flask import Flask, request, jsonify
from paddleocr import PaddleOCR
from pdf2image import convert_from_bytes
import docx
import io
import numpy as np
from PIL import Image
import sys
import gc

app = Flask(__name__)

# Inisialisasi PaddleOCR sekali saja di tingkat global (bahasa Indonesia & Inggris)
# use_gpu=False agar aman berjalan di CPU Railway
ocr = PaddleOCR(use_angle_cls=True, lang='id', use_gpu=False, show_log=False)

def extract_from_pdf(pdf_bytes):
    # Gunakan DPI 200 agar seimbang antara akurasi dan penggunaan RAM
    images = convert_from_bytes(pdf_bytes, dpi=200)
    full_text = []
    
    for i, img in enumerate(images):
        img_np = np.array(img.convert("RGB"))
        result = ocr.ocr(img_np, cls=True)
        
        page_lines = []
        if result and result[0]:
            for line in result[0]:
                # line[1][0] berisi string teks hasil ekstraksi
                text_content = line[1][0]
                page_lines.append(text_content)
                
        full_text.append(f"--- [HALAMAN {i+1}] ---\n" + "\n".join(page_lines))
        
        del img
        del img_np
        gc.collect()
        
    return "\n\n".join(full_text), len(images)

def extract_from_image(file_bytes):
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    img_np = np.array(img)
    result = ocr.ocr(img_np, cls=True)
    
    page_lines = []
    if result and result[0]:
        for line in result[0]:
            page_lines.append(line[1][0])
            
    return "\n".join(page_lines)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "PaddleOCR Multi-Format Service Active"})

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
            extracted_text = extract_from_image(file_bytes)
            total_pages = 1
        elif filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file_bytes))
            extracted_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            total_pages = 1
        else:
            return jsonify({"success": False, "error": "Format file tidak didukung"}), 400

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
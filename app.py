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

# Inisialisasi PaddleOCR (use_angle_cls sudah menangani orientasi teks)
ocr = PaddleOCR(use_angle_cls=True, lang='id')

def parse_paddle_result(result):
    """
    Fungsi pembantu untuk mengekstrak string teks dari output PaddleOCR v3 / v2
    """
    page_lines = []
    if not result:
        return ""

    for line in result:
        if not line:
            continue
        # Format PaddleOCR: [ [ [box_coords], (text, confidence) ], ... ]
        for item in line:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                # Jika elemen kedua adalah tuple (text, confidence)
                if isinstance(item[1], (list, tuple)):
                    page_lines.append(str(item[1][0]))
                # Format objek/dict jika menggunakan PaddleX pipeline
                elif hasattr(item[1], "text"):
                    page_lines.append(str(item[1].text))
            elif isinstance(item, str):
                page_lines.append(item)
                
    return "\n".join(page_lines)

def extract_from_pdf(pdf_bytes):
    images = convert_from_bytes(pdf_bytes, dpi=200)
    full_text = []
    
    for i, img in enumerate(images):
        img_np = np.array(img.convert("RGB"))
        
        # HAPUS cls=True di sini!
        result = ocr.ocr(img_np)
        
        extracted_page_text = parse_paddle_result(result)
        full_text.append(f"--- [HALAMAN {i+1}] ---\n{extracted_page_text}")
        
        del img
        del img_np
        gc.collect()
        
    return "\n\n".join(full_text), len(images)

def extract_from_image(file_bytes):
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    img_np = np.array(img)
    
    # HAPUS cls=True di sini!
    result = ocr.ocr(img_np)
    
    return parse_paddle_result(result)

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
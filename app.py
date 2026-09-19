from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes
import docx
import io
import cv2
import numpy as np
from PIL import Image
import sys
import gc

app = Flask(__name__)

def preprocess_image_advanced(pil_image):
    open_cv_image = np.array(pil_image.convert("RGB"))
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)

def extract_from_pdf(pdf_bytes):
    images = convert_from_bytes(pdf_bytes, dpi=300)
    full_text = []
    custom_config = r'--oem 3 --psm 6'
    
    for i, img in enumerate(images):
        processed_img = preprocess_image_advanced(img)
        try:
            text = pytesseract.image_to_string(processed_img, lang="ind+eng", config=custom_config)
        except Exception:
            text = pytesseract.image_to_string(processed_img, lang="eng", config=custom_config)
            
        full_text.append(f"--- [HALAMAN {i+1}] ---\n{text}")
        
        # Free memory gambar yang sudah di-OCR
        del img
        del processed_img
        gc.collect()
        
    return "\n\n".join(full_text), len(images)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Optimized Tesseract Active"})

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
            img = Image.open(io.BytesIO(file_bytes))
            processed_img = preprocess_image_advanced(img)
            extracted_text = pytesseract.image_to_string(processed_img, lang="ind+eng", config=r'--oem 3 --psm 6')
            total_pages = 1
        elif filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file_bytes))
            extracted_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            total_pages = 1
        else:
            return jsonify({"success": False, "error": "Format file tidak didukung"}), 400

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
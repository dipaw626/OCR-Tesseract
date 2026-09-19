from flask import Flask, request, jsonify
import easyocr
from pdf2image import convert_from_bytes
import docx
import io
import numpy as np
from PIL import Image
import sys

app = Flask(__name__)

# Load Reader sekali saat startup agar tidak berat di setiap request
# ['id', 'en'] mendukun bahasa Indonesia & Inggris
reader = easyocr.Reader(['id', 'en'], gpu=False)

def extract_from_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image_np = np.array(image)
    result = reader.readtext(image_np, detail=0)
    return "\n".join(result)

def extract_from_pdf(pdf_bytes):
    images = convert_from_bytes(pdf_bytes)
    full_text = []
    for i, image in enumerate(images):
        image_np = np.array(image)
        lines = reader.readtext(image_np, detail=0)
        full_text.append(f"--- [HALAMAN {i+1}] ---\n" + "\n".join(lines))
    return "\n\n".join(full_text), len(images)

def extract_from_docx(docx_bytes):
    doc = docx.Document(io.BytesIO(docx_bytes))
    full_text = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(full_text)

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

        extracted_text = ""
        total_pages = 1

        # Handling Multi-Format File
        if filename.endswith(".pdf"):
            extracted_text, total_pages = extract_from_pdf(file_bytes)
        elif filename.endswith((".png", ".jpg", ".jpeg")):
            extracted_text = extract_from_image(file_bytes)
        elif filename.endswith(".docx"):
            extracted_text = extract_from_docx(file_bytes)
        else:
            return jsonify({"success": False, "error": "Format file tidak didukung (.pdf, .png, .jpg, .docx)"}), 400

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
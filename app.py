from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes
import docx
import io
from PIL import Image, ImageEnhance, ImageFilter
import sys

app = Flask(__name__)

def preprocess_image(image):
    # Convert ke Grayscale & naikkan kontras agar teks tabel lebih tajam bagi Tesseract
    image = image.convert("L")
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    return image

def extract_from_pdf(pdf_bytes):
    images = convert_from_bytes(pdf_bytes, dpi=200)
    full_text = []
    
    for i, img in enumerate(images):
        processed_img = preprocess_image(img)
        try:
            text = pytesseract.image_to_string(processed_img, lang="ind+eng")
        except Exception:
            text = pytesseract.image_to_string(processed_img, lang="eng")
            
        full_text.append(f"--- [HALAMAN {i+1}] ---\n{text}")
        
    return "\n\n".join(full_text), len(images)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Tesseract Multi-Format Service Active"})

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
            processed_img = preprocess_image(img)
            extracted_text = pytesseract.image_to_string(processed_img, lang="ind+eng")
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
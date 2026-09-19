from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes
from pypdf import PdfReader
import docx
import io
from PIL import Image, ImageEnhance
import sys
import gc

app = Flask(__name__)

def preprocess_image(image):
    """
    Pre-processing sedang (1.3x Contrast) agar piksel karakter tipis
    seperti underscore (_), titik (.), dan simbol ($) tidak hilang.
    """
    gray = image.convert("L")
    enhancer = ImageEnhance.Contrast(gray)
    return enhancer.enhance(1.3)

def extract_from_pdf(pdf_bytes):
    # --- LANGKAH 1: Coba Native Extraction via pypdf (100% Akurat & Super Cepat) ---
    try:
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        native_pages = []
        total_native_chars = 0
        
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text_cleaned = text.strip()
            total_native_chars += len(text_cleaned)
            native_pages.append(f"--- [HALAMAN {i+1}] ---\n{text_cleaned}")
            
        # Ambang batas: Jika total karakter terdeteksi > 50, berarti ini Real Text PDF
        if total_native_chars > 50:
            return "\n\n".join(native_pages), len(reader.pages), "pypdf_native"
            
    except Exception as e:
        print(f"--> Native PDF Extraction Bypass: {str(e)}", file=sys.stderr)

    # --- LANGKAH 2: Fallback ke Tesseract OCR (Jika PDF berupa Scan/Gambar) ---
    images = convert_from_bytes(pdf_bytes, dpi=200)
    full_text = []
    
    for i, img in enumerate(images):
        processed_img = preprocess_image(img)
        
        try:
            text = pytesseract.image_to_string(processed_img, lang="ind+eng")
        except Exception:
            text = pytesseract.image_to_string(processed_img, lang="eng")
            
        full_text.append(f"--- [HALAMAN {i+1}] ---\n{text}")
        
        # Hapus instance gambar dari memori untuk mencegah RAM OOM di Railway
        del img
        del processed_img
        gc.collect()
        
    return "\n\n".join(full_text), len(images), "tesseract_ocr"

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Universal Multi-Format Extractor Active"})

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
        method_used = "native"

        # 1. Handling PDF File (Hybrid: Native vs OCR)
        if filename.endswith(".pdf"):
            extracted_text, total_pages, method_used = extract_from_pdf(file_bytes)

        # 2. Handling Image File (PNG, JPG, JPEG)
        elif filename.endswith((".png", ".jpg", ".jpeg")):
            method_used = "tesseract_ocr"
            img = Image.open(io.BytesIO(file_bytes))
            processed_img = preprocess_image(img)
            try:
                extracted_text = pytesseract.image_to_string(processed_img, lang="ind+eng")
            except Exception:
                extracted_text = pytesseract.image_to_string(processed_img, lang="eng")
            total_pages = 1

        # 3. Handling DOCX File
        elif filename.endswith(".docx"):
            method_used = "docx_native"
            doc = docx.Document(io.BytesIO(file_bytes))
            extracted_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            total_pages = 1

        else:
            return jsonify({"success": False, "error": "Format file tidak didukung (.pdf, .png, .jpg, .jpeg, .docx)"}), 400

        # Paksa Garbage Collector membersihkan RAM sisa
        gc.collect()

        return jsonify({
            "success": True,
            "total_pages": total_pages,
            "extraction_method": method_used,
            "text": extracted_text
        })

    except Exception as e:
        print(f"--> Processing Error: {str(e)}", file=sys.stderr, flush=True)
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes
import docx
import io
from PIL import Image, ImageEnhance, ImageFilter
import sys
import gc

app = Flask(__name__)

def preprocess_image(image):
    # 1. Ubah ke Grayscale
    gray = image.convert("L")
    
    # 2. Pertajam tepi huruf (membantu membaca _, $, dan teks kecil)
    sharpened = gray.filter(ImageFilter.SHARPEN)
    
    # 3. Kontras 1.5x (Jangan 2.0x agar piksel tipis pada huruf tidak hancur)
    enhancer = ImageEnhance.Contrast(sharpened)
    return enhancer.enhance(1.5)

def extract_from_pdf(pdf_bytes):
    # DPI 300 adalah standar wajib OCR agar simbol spesifik tidak terlewat
    images = convert_from_bytes(pdf_bytes, dpi=300)
    full_text = []
    
    # --oem 3 : Pakai engine LSTM (Deep Learning Tesseract)
    # --psm 6 : Membaca halaman sebagai satu blok teks rata (mencegah teks lompat halaman)
    custom_config = r'--oem 3 --psm 6'
    
    for i, img in enumerate(images):
        processed_img = preprocess_image(img)
        
        try:
            text = pytesseract.image_to_string(processed_img, lang="ind+eng", config=custom_config)
        except Exception:
            text = pytesseract.image_to_string(processed_img, lang="eng", config=custom_config)
            
        full_text.append(f"--- [HALAMAN {i+1}] ---\n{text}")
        
        # Cegah OOM di Railway: Hapus image object dari RAM setelah di-OCR
        del img
        del processed_img
        gc.collect()
        
    return "\n\n".join(full_text), len(images)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Optimized Tesseract Multi-Format Active"})

@app.route("/ocr", methods=["POST"])
def process_ocr():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file = request.files["file"]
        filename = file.filename.lower()
        file_bytes = file.read()

        custom_config = r'--oem 3 --psm 6'

        if filename.endswith(".pdf"):
            extracted_text, total_pages = extract_from_pdf(file_bytes)
        elif filename.endswith((".png", ".jpg", ".jpeg")):
            img = Image.open(io.BytesIO(file_bytes))
            processed_img = preprocess_image(img)
            extracted_text = pytesseract.image_to_string(processed_img, lang="ind+eng", config=custom_config)
            total_pages = 1
        elif filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file_bytes))
            extracted_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            total_pages = 1
        else:
            return jsonify({"success": False, "error": "Format file tidak didukung"}), 400

        # Panggil Garbage Collector untuk endpoint utama
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
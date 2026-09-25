import io
import gc
import sys
import numpy as np
import cv2
import docx
from PIL import Image, ImageOps
import pytesseract
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
from pypdf import PdfReader
from flask import Flask, request, jsonify

app = Flask(__name__)

def advanced_preprocess_image(pil_img: Image.Image) -> Image.Image:
    """
    Advanced OCR Pre-processing Pipeline:
    1. EXIF Orientation Fix (Menangani foto miring/terbalik dari HP).
    2. Upscaling (Jika resolusi gambar terlalu rendah).
    3. Grayscale conversion.
    4. Adaptive Thresholding via OpenCV (Menghilangkan bayangan & kontras tidak merata).
    """
    # 1. Autofix orientasi EXIF dari kamera HP
    pil_img = ImageOps.exif_transpose(pil_img)

    # Convert PIL ke OpenCV Format (BGR -> GRAY)
    open_cv_image = np.array(pil_img.convert("RGB"))
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)

    # 2. Resizing/Upscaling jika gambar terlalu kecil (DPI Rendah)
    height, width = gray.shape[:2]
    if height < 1000 or width < 1000:
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # 3. Denoising untuk menghilangkan bintik-bintik hasil scan
    denoised = cv2.fastNlMeansDenoising(gray, h=10, searchWindowSize=21, templateWindowSize=7)

    # 4. Otsu / Adaptive Thresholding (Membuat background putih & teks hitam pekat)
    # Sangat efektif memisahkan teks tipis (_, ., $) dari bayangan foto
    binary_img = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )

    return Image.fromarray(binary_img)


def extract_from_pdf(pdf_bytes: bytes) -> tuple[str, int, str]:
    # --- LANGKAH 1: Native Extraction via pypdf ---
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

        if total_native_chars > 50:
            return "\n\n".join(native_pages), len(reader.pages), "pypdf_native"

    except Exception as e:
        print(f"--> Native PDF Extraction Bypass: {str(e)}", file=sys.stderr)

    # --- LANGKAH 2: Fallback Stream OCR (300 DPI Page-by-Page) ---
    info = pdfinfo_from_bytes(pdf_bytes)
    total_pages = info.get("Pages", 1)
    full_text = []

    # Omit PSM/OEM config bawaan & set OMP_THREAD_LIMIT via env
    custom_config = r'--oem 3 --psm 6'

    for page_num in range(1, total_pages + 1):
        # Gunakan 300 DPI per halaman tunggal untuk mencegah OOM Spike
        images = convert_from_bytes(
            pdf_bytes,
            dpi=300,
            first_page=page_num,
            last_page=page_num
        )
        if not images:
            continue

        img = images[0]
        processed_img = advanced_preprocess_image(img)

        try:
            text = pytesseract.image_to_string(
                processed_img, lang="ind+eng", config=custom_config
            )
        except pytesseract.TesseractError:
            text = pytesseract.image_to_string(
                processed_img, lang="eng", config=custom_config
            )

        full_text.append(f"--- [HALAMAN {page_num}] ---\n{text}")

        # Strict Cleanup Memori Per Halaman
        del img, processed_img, images
        gc.collect()

    return "\n\n".join(full_text), total_pages, "tesseract_ocr"


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

        if not file_bytes:
            return jsonify({"success": False, "error": "Empty file uploaded"}), 400

        extracted_text = ""
        total_pages = 1
        method_used = "native"

        if filename.endswith(".pdf"):
            extracted_text, total_pages, method_used = extract_from_pdf(file_bytes)

        elif filename.endswith((".png", ".jpg", ".jpeg")):
            method_used = "tesseract_ocr"
            img = Image.open(io.BytesIO(file_bytes))
            processed_img = advanced_preprocess_image(img)
            
            custom_config = r'--oem 3 --psm 6'
            try:
                extracted_text = pytesseract.image_to_string(
                    processed_img, lang="ind+eng", config=custom_config
                )
            except pytesseract.TesseractError:
                extracted_text = pytesseract.image_to_string(
                    processed_img, lang="eng", config=custom_config
                )
            total_pages = 1

            del img, processed_img

        elif filename.endswith(".docx"):
            method_used = "docx_native"
            doc = docx.Document(io.BytesIO(file_bytes))
            extracted_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            total_pages = 1

        else:
            return jsonify({
                "success": False, 
                "error": "Format file tidak didukung (.pdf, .png, .jpg, .jpeg, .docx)"
            }), 400

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
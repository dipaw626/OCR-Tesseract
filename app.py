import io
import gc
import sys
import re
import numpy as np
import cv2
import docx
from PIL import Image, ImageOps
import pytesseract
from pdf2image import convert_from_bytes
from pypdf import PdfReader
from flask import Flask, request, jsonify

app = Flask(__name__)

def advanced_preprocess_image(pil_img: Image.Image) -> Image.Image:
    """
    Advanced OCR Pre-processing Pipeline (100% Full Canvas Image):
    1. EXIF Orientation Fix.
    2. Resizing / Upscaling jika resolusi gambar rendah.
    3. Denoising & Adaptive Thresholding via OpenCV.
    """
    pil_img = ImageOps.exif_transpose(pil_img)

    open_cv_image = np.array(pil_img.convert("RGB"))
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)

    height, width = gray.shape[:2]

    if height < 1000 or width < 1000:
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    denoised = cv2.fastNlMeansDenoising(gray, h=10, searchWindowSize=21, templateWindowSize=7)

    binary_img = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )

    return Image.fromarray(binary_img)


def advanced_regex_cleaner(text: str) -> str:
    """
    Preservation-First Regex Cleaner:
    1. DROP SELURUH HALAMAN: Jika halaman mengandung 'KETENTUAN PEMBATALAN', return "" (KOSONG).
    2. POTONG HEADER LOGO: Untuk halaman utama (misal 'FORMULIR PENDAFTARAN'),
       potong SEMUA baris/logo acak di atas judul tersebut.
    3. CLEANUP NOISE: Hapus watermark CamScanner & URL footer pada halaman tersisa.
    """
    if not text:
        return ""

    # --- LANGKAH 1: IF PAGE CONTAINS 'KETENTUAN PEMBATALAN' -> DROP 100% ---
    if re.search(r"KETENTUAN\s+PEMBATALAN", text, re.IGNORECASE):
        return "[HALAMAN KETENTUAN PEMBATALAN DIABAIKAN]"

    lines = text.splitlines()

    # --- LANGKAH 2: POTONG LOGO / HEADER DI ATAS FORMULIR PENDAFTARAN ---
    top_header_anchors = [
        r"FORMULIR\s+PENDAFTARAN"
    ]

    top_anchor_idx = -1
    for idx, line in enumerate(lines):
        for pattern in top_header_anchors:
            if re.search(pattern, line, re.IGNORECASE):
                top_anchor_idx = idx
                break
        if top_anchor_idx != -1:
            break

    # Potong semua baris/logo di atas 'FORMULIR PENDAFTARAN'
    if top_anchor_idx != -1:
        lines = lines[top_anchor_idx:]

    # --- LANGKAH 3: PEMBERSIHAN FOOTER STANDARD (Watermark & URL Footer) ---
    noise_patterns = [
        r"(?i)our\s+partner",
        r"(?i)dipindai\s+dengan\s+camscanner",
        r"(?i)scanned\s+with\s+camscanner",
        r"(?i)komplek\s+perum\s+puri\s+gentan",
        r"(?i)jalan\s+kaliurang",
        r"(?i)https?://[^\s]+",
        r"mail@expertindo-training\.com",
        r"expertindotraining@gmail\.com",
    ]

    cleaned_lines = []
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue

        if any(re.search(pat, stripped_line) for pat in noise_patterns):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def extract_from_pdf(pdf_bytes: bytes) -> tuple[str, int, str]:
    pdf_file = io.BytesIO(pdf_bytes)
    reader = PdfReader(pdf_file)
    total_pages = len(reader.pages)
    
    full_text = []
    methods_used = set()
    
    custom_config = r'--oem 3 --psm 6'

    for i, page in enumerate(reader.pages):
        page_num = i + 1
        native_text = (page.extract_text() or "").strip()
        
        # JIKA NATIVE TEXT (Digital PDF > 30 Karakter)
        if len(native_text) > 30:
            cleaned_native = advanced_regex_cleaner(native_text)
            full_text.append(f"--- [HALAMAN {page_num}] ---\n{cleaned_native}")
            methods_used.add("pypdf_native")
        else:
            # JIKA SCAN / GAMBAR: Full Page OCR (300 DPI) + Regex Cleaning
            methods_used.add("tesseract_ocr")
            
            images = convert_from_bytes(
                pdf_bytes,
                dpi=300,
                first_page=page_num,
                last_page=page_num
            )
            
            if images:
                img = images[0]
                processed_img = advanced_preprocess_image(img)
                
                try:
                    ocr_text = pytesseract.image_to_string(
                        processed_img, lang="ind+eng", config=custom_config
                    )
                except pytesseract.TesseractError:
                    ocr_text = pytesseract.image_to_string(
                        processed_img, lang="eng", config=custom_config
                    )
                
                cleaned_text = advanced_regex_cleaner(ocr_text)
                full_text.append(f"--- [HALAMAN {page_num}] ---\n{cleaned_text}")
                
                del img, processed_img, images
                gc.collect()

    final_method = "+".join(sorted(methods_used))
    return "\n\n".join(full_text), total_pages, final_method


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
            
            extracted_text = advanced_regex_cleaner(extracted_text)
            total_pages = 1

            del img, processed_img

        elif filename.endswith(".docx"):
            method_used = "docx_native"
            doc = docx.Document(io.BytesIO(file_bytes))
            raw_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            extracted_text = advanced_regex_cleaner(raw_text)
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
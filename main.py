from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Tesseract OCR Service Active"})

@app.route("/ocr", methods=["POST"])
def process_ocr():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        pdf_bytes = file.read()

        images = convert_from_bytes(pdf_bytes)

        full_text = []
        for i, image in enumerate(images):
            text = pytesseract.image_to_string(image, lang="ind+eng")
            full_text.append(f"--- [HALAMAN {i+1}] ---\n{text}")

        return jsonify({
            "success": True,
            "total_pages": len(images),
            "text": "\n\n".join(full_text)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
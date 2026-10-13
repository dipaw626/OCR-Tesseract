const path = require('path');
const { createWorker } = require('tesseract.js');
const Busboy = require('busboy');
const pdfImgConvert = require('pdf-img-convert');

export const config = {
  api: {
    bodyParser: false, // Wajib false untuk terima multipart/form-data dari Apps Script
  },
};

export default async function handler(req, res) {
  if (req.method === 'GET') {
    return res.status(200).json({ status: "Vercel Tesseract WASM Engine Active" });
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }

  let worker = null;

  try {
    const busboy = Busboy({ headers: req.headers });
    let fileBuffer = [];
    let filename = "";

    busboy.on('file', (fieldname, file, info) => {
      filename = (info && info.filename) ? info.filename.toLowerCase() : "";
      file.on('data', (data) => fileBuffer.push(data));
    });

    busboy.on('finish', async () => {
      try {
        const buffer = Buffer.concat(fileBuffer);

        if (!buffer || buffer.length === 0) {
          return res.status(400).json({ success: false, error: "File buffer kosong" });
        }

        // Tunjuk path tesseract-core di node_modules Vercel
        const corePath = path.join(process.cwd(), 'node_modules', 'tesseract.js-core');

        // Inisialisasi Tesseract Worker
        worker = await createWorker('ind+eng', 1, {
          corePath: corePath,
          cachePath: '/tmp',
        });

        await worker.setParameters({
          tessedit_pageseg_mode: '6',
        });

        let extractedTexts = [];

        // 🟢 DETEKSI: Jika file adalah PDF, konversi ke Gambar PNG per halaman terlebih dahulu
        if (filename.endsWith('.pdf') || buffer.slice(0, 4).toString() === '%PDF') {
          // Konversi PDF ke Array of Image Buffers (PNG) pada DPI 150
          const outputImages = await pdfImgConvert.convert(buffer, {
            scale: 1.5 // Setara ~150-200 DPI (Cukup tajam untuk OCR)
          });

          for (let i = 0; i < outputImages.length; i++) {
            const { data: { text } } = await worker.recognize(outputImages[i]);
            if (text && text.trim()) {
              extractedTexts.push(text.trim());
            }
          }
        } else {
          // 🟢 JIKA FILE ADALAH GAMBAR (PNG / JPG / WEBP)
          const { data: { text } } = await worker.recognize(buffer);
          if (text && text.trim()) {
            extractedTexts.push(text.trim());
          }
        }

        await worker.terminate();

        return res.status(200).json({
          success: true,
          total_pages: extractedTexts.length,
          extraction_method: "tesseract_wasm_node",
          text: extractedTexts.join("\n\n")
        });

      } catch (err) {
        if (worker) await worker.terminate();
        return res.status(500).json({ success: false, error: err.message });
      }
    });

    req.pipe(busboy);

  } catch (error) {
    if (worker) await worker.terminate();
    return res.status(500).json({ success: false, error: error.message });
  }
}
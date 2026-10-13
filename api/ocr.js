const path = require('path');
const { createWorker } = require('tesseract.js');
const Busboy = require('busboy');
const pdfParse = require('pdf-parse');

export const config = {
  api: {
    bodyParser: false, // Wajib false untuk terima multipart/form-data
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

        let extractedText = "";
        let isPdf = filename.endsWith('.pdf') || buffer.slice(0, 4).toString() === '%PDF';

        // 1. JIKA FILE ADALAH PDF: Coba ekstrak layer teks langsung pakai pdf-parse (Super Cepat & Bebas Error C++)
        if (isPdf) {
          try {
            const pdfData = await pdfParse(buffer);
            if (pdfData.text && pdfData.text.trim().length > 20) {
              return res.status(200).json({
                success: true,
                total_pages: pdfData.numpages || 1,
                extraction_method: "pdf_text_native",
                text: pdfData.text.trim()
              });
            }
          } catch (pdfErr) {
            console.log("pdf-parse gagal/PDF berupa gambar scan, melanjut ke Tesseract WASM...");
          }
        }

        // 2. JIKA PDF BERUPA SCAN GAMBAR ATAU FILE ADALAH GAMBAR (PNG/JPG): Gunakan Tesseract WASM
        const corePath = path.join(process.cwd(), 'node_modules', 'tesseract.js-core');

        worker = await createWorker('ind+eng', 1, {
          corePath: corePath,
          cachePath: '/tmp',
        });

        await worker.setParameters({
          tessedit_pageseg_mode: '6',
        });

        const { data: { text } } = await worker.recognize(buffer);
        await worker.terminate();

        return res.status(200).json({
          success: true,
          total_pages: 1,
          extraction_method: "tesseract_wasm_node",
          text: text ? text.trim() : ""
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
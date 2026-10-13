const path = require('path');
const { createWorker } = require('tesseract.js');
const Busboy = require('busboy');
const pdfParse = require('pdf-parse');
const { PDFDocument, PDFName, PDFRawStream } = require('pdf-lib');

export const config = {
  api: {
    bodyParser: false,
  },
};

// --- REGEX CLEANER PORTINGAN DARI PYTHON RAILWAY ---
function advancedRegexCleaner(text) {
  if (!text) return "";

  // 1. DROP HALAMAN KETENTUAN PEMBATALAN
  if (/KETENTUAN\s+PEMBATALAN/i.test(text)) {
    return "[HALAMAN KETENTUAN PEMBATALAN DIABAIKAN]";
  }

  let lines = text.split(/\r?\n/);

  // 2. POTONG LOGO/HEADER DI ATAS FORMULIR PENDAFTARAN
  let topAnchorIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (/FORMULIR\s+PENDAFTARAN/i.test(lines[i])) {
      topAnchorIdx = i;
      break;
    }
  }

  if (topAnchorIdx !== -1) {
    lines = lines.slice(topAnchorIdx);
  }

  // 3. PEMBERSIHAN FOOTER & NOISE
  const noisePatterns = [
    /our\s+partner/i,
    /dipindai\s+dengan\s+camscanner/i,
    /scanned\s+with\s+camscanner/i,
    /komplek\s+perum\s+puri\s+gentan/i,
    /jalan\s+kaliurang/i,
    /https?:\/\/[^\s]+/i,
    /mail@expertindo-training\.com/i,
    /expertindotraining@gmail\.com/i
  ];

  let cleanedLines = lines.filter(line => {
    let str = line.trim();
    if (!str) return false;
    return !noisePatterns.some(pat => pat.test(str));
  });

  return cleanedLines.join("\n").trim();
}

// Extract Embedded Image Buffers dari PDF secara murni pakai pdf-lib (0% C++ Canvas)
async function extractEmbeddedImagesFromPdf(pdfBuffer) {
  const images = [];
  try {
    const pdfDoc = await PDFDocument.load(pdfBuffer);
    const pages = pdfDoc.getPages();

    for (const page of pages) {
      const { node } = page;
      const resources = node.Resources();
      if (!resources) continue;

      const xObjects = resources.get(PDFName.of('XObject'));
      if (!xObjects) continue;

      const xObjectKeys = xObjects.keys();
      for (const key of xObjectKeys) {
        const xObject = xObjects.get(key);
        if (xObject instanceof PDFRawStream) {
          const subtype = xObject.dict.get(PDFName.of('Subtype'));
          if (subtype === PDFName.of('Image')) {
            const imgBuffer = Buffer.from(xObject.getContents());
            if (imgBuffer && imgBuffer.length > 5000) { // Saring icon/image kerdil
              images.push(imgBuffer);
            }
          }
        }
      }
    }
  } catch (e) {
    console.log("Error extracting embedded images:", e.message);
  }
  return images;
}

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

        let isPdf = filename.endsWith('.pdf') || buffer.slice(0, 4).toString() === '%PDF';
        let fullRawText = "";
        let totalPages = 1;

        // 1. Ekstrak Teks Native PDF (jika ada)
        if (isPdf) {
          try {
            const pdfData = await pdfParse(buffer);
            fullRawText = pdfData.text || "";
            totalPages = pdfData.numpages || 1;
          } catch (e) {}
        }

        // 2. Jika File Gambar PNG/JPG
        if (!isPdf) {
          const corePath = path.join(process.cwd(), 'node_modules', 'tesseract.js-core');
          worker = await createWorker('ind+eng', 1, {
            corePath: corePath,
            cachePath: '/tmp',
          });
          await worker.setParameters({ tessedit_pageseg_mode: '6' });

          const { data: { text } } = await worker.recognize(buffer);
          fullRawText = text;
          await worker.terminate();
        } 
        // 3. Jika File PDF & mengandung Gambar Scan: Bongkar Gambar Murni dari PDF lalu OCR
        else {
          const embeddedImages = await extractEmbeddedImagesFromPdf(buffer);
          
          if (embeddedImages.length > 0) {
            const corePath = path.join(process.cwd(), 'node_modules', 'tesseract.js-core');
            worker = await createWorker('ind+eng', 1, {
              corePath: corePath,
              cachePath: '/tmp',
            });
            await worker.setParameters({ tessedit_pageseg_mode: '6' });

            for (const imgBuf of embeddedImages) {
              try {
                const { data: { text } } = await worker.recognize(imgBuf);
                if (text && text.trim()) {
                  fullRawText += "\n\n" + text.trim();
                }
              } catch (ocrErr) {
                console.log("OCR Image Stream skip:", ocrErr.message);
              }
            }
            await worker.terminate();
          }
        }

        // 4. Bersihkan Teks dengan Regex Cleaner
        const cleanedText = advancedRegexCleaner(fullRawText);

        return res.status(200).json({
          success: true,
          total_pages: totalPages,
          extraction_method: isPdf ? "pdf_hybrid_embedded_wasm" : "tesseract_wasm_image",
          text: cleanedText
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
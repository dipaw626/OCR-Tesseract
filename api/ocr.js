const path = require('path');
const { createWorker } = require('tesseract.js');
const Busboy = require('busboy');
const pdfParse = require('pdf-parse');

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

        // Step 1: Ambil Teks Native PDF (jika ada)
        if (isPdf) {
          try {
            const pdfData = await pdfParse(buffer);
            fullRawText = pdfData.text || "";
            totalPages = pdfData.numpages || 1;
          } catch (e) {}
        }

        // Step 2: Jika Teks Native Kosong / Kurang Lengkap, Pakai Tesseract WASM
        if (!isPdf || fullRawText.trim().length < 50) {
          const corePath = path.join(process.cwd(), 'node_modules', 'tesseract.js-core');

          worker = await createWorker('ind+eng', 1, {
            corePath: corePath,
            cachePath: '/tmp',
          });

          await worker.setParameters({
            tessedit_pageseg_mode: '6',
          });

          const { data: { text } } = await worker.recognize(buffer);
          fullRawText += "\n" + text;
          await worker.terminate();
        }

        // Step 3: Bersihkan Hasil dengan Regex Cleaner
        const cleanedText = advancedRegexCleaner(fullRawText);

        return res.status(200).json({
          success: true,
          total_pages: totalPages,
          extraction_method: "vercel_wasm_hybrid",
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
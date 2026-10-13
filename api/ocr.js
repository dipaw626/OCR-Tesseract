const path = require('path');
const { createWorker } = require('tesseract.js');
const Busboy = require('busboy');

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

    busboy.on('file', (fieldname, file) => {
      file.on('data', (data) => fileBuffer.push(data));
    });

    busboy.on('finish', async () => {
      try {
        const buffer = Buffer.concat(fileBuffer);

        if (!buffer || buffer.length === 0) {
          return res.status(400).json({ success: false, error: "File buffer kosong" });
        }

        // Tunjuk langsung path tesseract-core di dalam node_modules Vercel
        const corePath = path.join(process.cwd(), 'node_modules', 'tesseract.js-core');

        // Inisialisasi worker dengan menunjuk corePath lokal
        worker = await createWorker('ind+eng', 1, {
          corePath: corePath,
          cachePath: '/tmp', // Izinkan simpan model bahasa sementara di folder /tmp Vercel
        });

        // Parameter PSM 6 (Single Uniform Block of Text)
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
const { createWorker } = require('tesseract.js');
const Busboy = require('busboy');

export const config = {
  api: {
    bodyParser: false, // Wajib false agar bisa terima multipart/form-data dari Apps Script
  },
};

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }

  try {
    const busboy = Busboy({ headers: req.headers });
    let fileBuffer = [];

    busboy.on('file', (fieldname, file) => {
      file.on('data', (data) => fileBuffer.push(data));
    });

    busboy.on('finish', async () => {
      const buffer = Buffer.concat(fileBuffer);

      // Inisialisasi Tesseract WASM Engine (Support Bahasa Indonesia & Inggris)
      const worker = await createWorker(['ind', 'eng']);
      
      // Set Parameter PSM (6 = Single Uniform Block of Text)
      await worker.setParameters({
        tessedit_pageseg_mode: '6',
      });

      const { data: { text } } = await worker.recognize(buffer);
      await worker.terminate();

      return res.status(200).json({
        success: true,
        total_pages: 1,
        extraction_method: "tesseract_wasm_node",
        text: text
      });
    });

    req.pipe(busboy);
  } catch (error) {
    return res.status(500).json({ success: false, error: error.message });
  }
}
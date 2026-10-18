import {
  extractReceipt,
  extractStatement,
  type DocumentExtraction,
} from "./document";

const MAX_BYTES = 10 * 1024 * 1024;
const MAX_PAGES = 20;
const MAX_PAGE_PIXELS = 12_000_000;
const MAX_JOB_PIXELS = 40_000_000;

function imageFormat(bytes: Uint8Array): "jpg" | "png" | "webp" | undefined {
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return "jpg";
  if (
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47
  )
    return "png";
  if (
    String.fromCharCode(...bytes.slice(0, 4)) === "RIFF" &&
    String.fromCharCode(...bytes.slice(8, 12)) === "WEBP"
  )
    return "webp";
}

async function ocr(blob: Blob, progress: (value: number) => void) {
  const { createWorker, OEM } = await import("tesseract.js");
  const worker = await createWorker("eng", OEM.LSTM_ONLY, {
    workerPath: "/ocr/worker.min.js",
    corePath: "/ocr/core",
    langPath: "/ocr/lang",
    logger: (message) => {
      if (message.status === "recognizing text") progress(message.progress);
    },
  });
  try {
    const result = await worker.recognize(
      blob,
      {},
      { text: true, blocks: true },
    );
    return { text: result.data.text, confidence: result.data.confidence / 100 };
  } finally {
    await worker.terminate();
  }
}

self.onmessage = async (
  event: MessageEvent<{
    file: File;
    documentType: DocumentExtraction["document_type"];
    forceOcr?: boolean;
  }>,
) => {
  const started = performance.now();
  try {
    const { file, documentType, forceOcr } = event.data;
    if (file.size > MAX_BYTES)
      throw new Error("Documents are limited to 10 MiB.");
    const bytes = new Uint8Array(await file.arrayBuffer());
    const isPdf = String.fromCharCode(...bytes.slice(0, 5)) === "%PDF-";
    const format = imageFormat(bytes);
    if (!isPdf && !format)
      throw new Error("The file signature is not PDF, JPG, PNG, or WebP.");
    let text = "",
      pages = 1,
      usedOcr = false,
      confidence = 1,
      totalPixels = 0;
    if (isPdf) {
      const pdfjs = await import("pdfjs-dist");
      pdfjs.GlobalWorkerOptions.workerSrc = new URL(
        "pdfjs-dist/build/pdf.worker.min.mjs",
        import.meta.url,
      ).toString();
      const pdf = await pdfjs.getDocument({ data: bytes, useSystemFonts: true })
        .promise;
      if (pdf.numPages > MAX_PAGES)
        throw new Error(`PDFs are limited to ${MAX_PAGES} pages.`);
      pages = pdf.numPages;
      const pageTexts: string[] = [];
      for (let pageNumber = 1; pageNumber <= pages; pageNumber++) {
        postMessage({
          progress: (pageNumber - 1) / pages,
          status: `Reading page ${pageNumber} of ${pages}`,
        });
        const page = await pdf.getPage(pageNumber);
        const content = await page.getTextContent({
          disableNormalization: false,
        });
        let previousY: number | undefined;
        let pageText = content.items
          .map((item) => {
            if (!("str" in item)) return "";
            const y = item.transform[5];
            const separator =
              previousY === undefined || Math.abs(y - previousY) < 2
                ? " "
                : "\n";
            previousY = y;
            return `${separator}${item.str}`;
          })
          .join("")
          .trim();
        if (pageNumber === 1 && !forceOcr && pageText.length >= 30) {
          const base = page.getViewport({ scale: 1 });
          const scale = Math.min(
            1.5,
            Math.sqrt(MAX_PAGE_PIXELS / (base.width * base.height)),
          );
          const viewport = page.getViewport({ scale });
          const canvas = new OffscreenCanvas(
            Math.ceil(viewport.width),
            Math.ceil(viewport.height),
          );
          await page.render({
            canvas: canvas as unknown as HTMLCanvasElement,
            canvasContext: canvas.getContext(
              "2d",
            )! as unknown as CanvasRenderingContext2D,
            viewport,
          }).promise;
          postMessage({
            preview: await canvas.convertToBlob({ type: "image/png" }),
          });
        }
        if (forceOcr || pageText.length < 30) {
          const base = page.getViewport({ scale: 1 });
          const scale = Math.min(
            2,
            Math.sqrt(MAX_PAGE_PIXELS / (base.width * base.height)),
          );
          const viewport = page.getViewport({ scale });
          const pixels = Math.ceil(viewport.width * viewport.height);
          totalPixels += pixels;
          if (pixels > MAX_PAGE_PIXELS || totalPixels > MAX_JOB_PIXELS)
            throw new Error("The rendered PDF exceeds the OCR pixel budget.");
          const canvas = new OffscreenCanvas(
            Math.ceil(viewport.width),
            Math.ceil(viewport.height),
          );
          await page.render({
            canvas: canvas as unknown as HTMLCanvasElement,
            canvasContext: canvas.getContext(
              "2d",
            )! as unknown as CanvasRenderingContext2D,
            viewport,
          }).promise;
          const rendered = await canvas.convertToBlob({ type: "image/png" });
          if (pageNumber === 1) postMessage({ preview: rendered });
          const result = await ocr(rendered, (value) =>
            postMessage({
              progress: (pageNumber - 1 + value) / pages,
              status: `OCR page ${pageNumber} of ${pages}`,
            }),
          );
          pageText = result.text;
          confidence = Math.min(confidence, result.confidence);
          usedOcr = true;
        }
        pageTexts.push(`[[PAGE ${pageNumber}]]\n${pageText}`);
        page.cleanup();
      }
      text = pageTexts.join("\n");
      await pdf.cleanup();
    } else {
      const bitmap = await createImageBitmap(file);
      totalPixels = bitmap.width * bitmap.height;
      bitmap.close();
      if (totalPixels > MAX_PAGE_PIXELS)
        throw new Error("Images are limited to 12 megapixels.");
      const result = await ocr(file, (value) =>
        postMessage({ progress: value, status: "Reading image locally" }),
      );
      text = result.text;
      confidence = result.confidence;
      usedOcr = true;
    }
    if (text.length > 200_000)
      throw new Error("Extracted text exceeds the safe review limit.");
    const receipt = extractReceipt(text);
    receipt.confidence = Math.min(receipt.confidence, confidence);
    postMessage({
      result: {
        document_type: documentType,
        source_format: isPdf ? "pdf" : format!,
        pages,
        used_ocr: usedOcr,
        elapsed_ms: Math.round(performance.now() - started),
        text,
        transactions: extractStatement(text),
        receipt,
      } satisfies DocumentExtraction,
    });
  } catch (error) {
    postMessage({
      error:
        error instanceof Error
          ? error.message
          : "The document could not be processed safely.",
    });
  }
};

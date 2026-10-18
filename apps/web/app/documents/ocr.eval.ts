import { createWorker, OEM } from "tesseract.js";
import { resolve } from "node:path";
import { readFile } from "node:fs/promises";
import { extractReceipt } from "./document.ts";
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";

const fixtures = [
  {
    name: "UK",
    path: "test-fixtures/uk-receipt.png",
    expected: [
      "GREEN MARKET",
      "18/10/2026",
      "Groceries",
      "25.00",
      "Wine",
      "12.00",
      "Household",
      "8.00",
      "TOTAL",
      "45.00",
      "VAT INCLUDED",
      "4.20",
    ],
    fields: {
      merchant: "GREEN MARKET",
      document_date: "2026-10-18",
      currency: "GBP",
      total: "45.00",
    },
  },
  {
    name: "India",
    path: "test-fixtures/india-receipt.png",
    expected: [
      "NANDINI STORE",
      "18/10/2026",
      "GSTIN",
      "Food",
      "100.00",
      "Discount",
      "10.00",
      "GST",
      "18.00",
      "TOTAL",
      "108.00",
      "UPI",
    ],
    fields: {
      merchant: "NANDINI STORE",
      document_date: "2026-10-18",
      currency: "INR",
      total: "108.00",
    },
  },
];

const worker = await createWorker("eng", OEM.LSTM_ONLY, {
  langPath: resolve("../../node_modules/@tesseract.js-data/eng/4.0.0_best_int"),
});
try {
  const results: object[] = [];
  for (const fixture of fixtures) {
    const started = performance.now();
    const { data } = await worker.recognize(resolve(fixture.path));
    const normalized = data.text.toLowerCase().replace(/\s+/g, " ");
    const tokensFound = fixture.expected.filter((token) =>
      normalized.includes(token.toLowerCase()),
    ).length;
    const receipt = extractReceipt(data.text);
    const fieldsCorrect = Object.entries(fixture.fields).filter(
      ([key, value]) =>
        String(receipt[key as keyof typeof receipt]).toUpperCase() ===
        value.toUpperCase(),
    ).length;
    results.push({
      fixture: fixture.name,
      ocr_confidence_percent: Number(data.confidence.toFixed(1)),
      evidence_token_accuracy_percent: Number(
        ((tokensFound / fixture.expected.length) * 100).toFixed(1),
      ),
      receipt_field_accuracy_percent: Number(
        ((fieldsCorrect / Object.keys(fixture.fields).length) * 100).toFixed(1),
      ),
      elapsed_ms: Math.round(performance.now() - started),
      extracted: {
        merchant: receipt.merchant,
        date: receipt.document_date,
        currency: receipt.currency,
        total: receipt.total,
        items: receipt.items.length,
      },
    });
  }
  const pdfStarted = performance.now();
  const pdf = await getDocument({
    data: new Uint8Array(
      await readFile(resolve("test-fixtures/uk-receipt.pdf")),
    ),
  }).promise;
  const page = await pdf.getPage(1);
  const content = await page.getTextContent();
  const pdfText = content.items
    .map((item) => ("str" in item ? item.str : ""))
    .join(" ");
  const pdfExpected = fixtures[0].expected;
  const pdfTokens = pdfExpected.filter((token) =>
    pdfText.toLowerCase().includes(token.toLowerCase()),
  ).length;
  results.push({
    fixture: "UK text PDF",
    ocr_confidence_percent: null,
    evidence_token_accuracy_percent: Number(
      ((pdfTokens / pdfExpected.length) * 100).toFixed(1),
    ),
    receipt_field_accuracy_percent: null,
    elapsed_ms: Math.round(performance.now() - pdfStarted),
    extracted: { pages: pdf.numPages, characters: pdfText.length },
  });
  await pdf.cleanup();
  console.log(JSON.stringify(results, null, 2));
} finally {
  await worker.terminate();
}

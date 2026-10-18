# Milestone C2: PDF, OCR and receipt intelligence

## Architecture

`/documents` extends the C1 browser-local boundary. A dedicated worker validates signatures and uses dynamically imported PDF.js 6.4.299 for text extraction and page rendering. Text-light or explicitly retried pages are rendered to bounded canvases and passed to Tesseract.js 7 with same-origin English trained data. JPG, PNG and WebP enter OCR directly. No original bytes or OCR text are sent to Gemini, another model, or the API.

The extraction result contains document type, source format, page count, OCR use, elapsed time, raw review text and typed receipt or statement candidates. Users select the document type and correct every financial field before staging. Unknown or unreconciled output remains a visible error rather than being invented.

## Limits and fallback

- Source file: 10 MiB.
- PDF: 20 pages.
- Image/rendered page: 12 megapixels.
- OCR job: 40 megapixels total.
- Extracted review text: 200,000 characters.
- Receipt lines: 100; scanned text lines considered: 500.
- UI watchdog: 60 seconds, after which the worker is terminated.

OCR assets total approximately 16.6 MB and load only when OCR is required. Text PDFs do not load Tesseract. Slow, unclear or unsupported documents retain preview and manual correction rather than uploading remotely.

## Financial integration

Receipt candidates preserve merchant, date, currency, quantity, unit price, line total, discount, tax/GST/VAT evidence, service charge, tip, rounding, total, confidence and line evidence. Browser arithmetic uses integer minor units; the server repeats reconciliation using `Decimal`.

Matching is deliberately conservative: same owner, expense direction, exact original amount and currency, date within three days, optional account, and merchant similarity evidence. The user must select and confirm the match. Linking replaces current categorization allocations only when categorized items reconcile exactly to the transaction total; it never creates another expense.

Reviewed receipt components are passed through session storage into the existing universal split builder. The existing group preview and largest-remainder allocation engine remain responsible for participant allocation and final reconciliation.

## Measured synthetic evaluation

Two clean 800×1000 synthetic fixtures were rendered and processed with the installed Tesseract engine and locally installed English trained data:

| Fixture | Tesseract confidence | Selected evidence tokens | Core fields | Warm OCR time |
|---|---:|---:|---:|---:|
| UK supermarket receipt | 95% | 12/12 (100%) | 4/4 (100%) | 198 ms |
| India GST/UPI receipt | 92% | 12/12 (100%) | 4/4 (100%) | 147 ms |
| UK text PDF | n/a | 12/12 (100%) | n/a | 76 ms |

Core fields are merchant, date, currency and final total. These results describe only the committed clean synthetic images on the evaluation machine. They do not establish accuracy for photographs, handwriting, unusual fonts, complex tables or real banks. The India fixture correctly identified discount, GST and total evidence but produced one ordinary purchasable item; editable review is therefore mandatory.

## Deliberate limitations

English OCR only; no handwriting guarantee, bank-specific PDF profile, table-layout reconstruction guarantee, legal GST/VAT interpretation or remote fallback. PDF statement row recovery uses conservative dated-line heuristics and routes results through C1 duplicate review. Complex statements and low-quality photographs may require manual correction or CSV/XLSX import. Milestone D capabilities are not enabled.

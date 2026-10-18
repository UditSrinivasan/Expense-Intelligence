# Security policy

## Reporting

Do not open public issues containing credentials, financial data, or vulnerability details. Use a private maintainer channel once one is configured. Until then, do not deploy this repository with real data.

## Current development-tool exception

`npm audit` reports GHSA-vfj7-8cjw-p6xm through `eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces`. The advisory affects denial of service from adversarial deeply nested glob patterns in the local/CI lint toolchain; these packages are development-only and are not included in the Next.js runtime bundle. As of 17 October 2026, npm reports `braces` 3.0.3 as latest while the advisory includes versions through 3.0.3, and its suggested fix is an incompatible ESLint-config downgrade.

This is a temporary, scoped exception—not a clean security scan. Do not pass untrusted glob patterns to lint commands. Recheck before every release and remove the exception when a compatible patched dependency exists. Owner: repository maintainer. Review/expiry: 17 November 2026.

## Financial document ingestion boundary

CSV and XLSX bytes remain in the browser and are parsed in a dedicated worker. The API receives only user-reviewed structured candidates plus a SHA-256 source identity; it does not receive or retain the original statement. Parsing is bounded to 10 MiB, 10,000 data rows, 100 columns, 2,000 characters per cell and 25 sheets. XLSX input must have a ZIP signature, formulas and external links are never executed, and formula-like text is held for review.

The server revalidates financial types, ownership, currency, category access and batch state. Import endpoints scope every query to the authenticated owner. Confirmation uses an optimistic version, row locking, a unique source-row transaction constraint and one database transaction. Duplicate matches are evidence for explicit review, never an automatic deletion or merge. Operational logs and audit events contain identifiers and actions, not imported descriptions or amounts.

PDF, JPG, PNG and WebP processing also remains browser-local. Signature checks precede parsing; limits are 10 MiB, 20 PDF pages, 12 megapixels per rendered page/image, 40 megapixels per OCR job, 200,000 extracted characters and a 60-second UI watchdog. PDF.js is used as a parser/renderer, not as an interactive viewer: annotations, links, forms and embedded scripts are not invoked. Tesseract workers and English trained data are served from this application’s origin and loaded only for images or scanned pages. Extracted text is untrusted data and is never interpreted as a prompt or instruction.

The API never accepts raw document bytes. Receipt candidates are revalidated with exact decimals, owner-scoped accounts/categories/transactions, optimistic versions and exact component reconciliation. Linking enriches an existing transaction and does not create a second expense. Audit records contain document identifiers, not OCR text or financial amounts.

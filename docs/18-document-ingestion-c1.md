# Milestone C1: browser-local document ingestion

## Delivered workflow

`/imports` provides account selection, local CSV/XLSX parsing, sheet choice, header and column mapping, explicit date-order confirmation, exact decimal normalization, per-row editing, bulk categorization, duplicate review, atomic confirmation and import history. It supports unfamiliar India and UK layouts through mapping rather than bank-specific claims.

The browser worker accepts CSV and XLSX only. CSV decoding tries strict UTF-8 and then Windows-1252, detects comma, semicolon, tab or pipe delimiters, and handles quoted fields. XLSX parsing reads a selected sheet without running macros, formulas, links or scripts. Limits are 10 MiB, 10,000 rows, 100 columns, 2,000 characters per cell and 25 sheets.

## Trust and data flow

```text
hostile file bytes
  -> bounded browser worker parser
  -> user mapping and local normalized preview
  -> reviewed structured candidates + source hash
  -> owner-scoped server staging and duplicate evidence
  -> explicit confirmation
  -> one atomic ledger transaction
```

Raw files are neither sent to the API nor retained. The source hash supports provenance and source identity without file storage. The API revalidates dates, exact positive decimal magnitudes, currencies, owner-scoped accounts/categories and unique source rows. Imported ledger records reuse the existing transaction, allocation, categorization, FX, budget and dashboard paths.

## Recognition and duplicate policy

Transaction recognition is deterministic and conservative. Refund markers become refunds; explicit own-account markers become transfers; UPI, NEFT, IMPS, Faster Payment and generic bank-transfer rails remain transfer candidates requiring review because the rail alone does not establish consumption. Credits otherwise remain income and debits default to purchases. Approved user merchant rules may suggest a category, but imports never create rules.

Exact duplicate evidence uses an account-scoped reference or the same date, exact amount, currency, direction and normalized description. A matching description and financial identity within three days is only a likely duplicate. Both require a user decision; candidates are never silently merged or deleted.

## Persistence and concurrency

Migration `0006_imports` adds financial accounts, import batches, staged rows, user mapping profiles and nullable transaction provenance. Confirmation locks the owner-scoped batch, checks its optimistic version, rejects unresolved rows, writes all approved transactions and allocations in one commit, and records an audit event. Repeating confirmation returns the already-confirmed result. A unique `transactions.import_row_id` constraint is the final duplicate-write guard.

## Future adapter contract

Future text-PDF, scanned-PDF, image, receipt and chat-attachment adapters must stop at the same reviewable candidate boundary. They may add extraction-specific evidence, including receipt item, quantity, unit price, discount, tax, tip and service-charge fields, but must reuse server validation, categorization, duplicate review, explicit confirmation and the existing ledger. Real financial documents remain outside the synthetic-only Gemini boundary.

## Deliberate limitations

`.xls`, PDF, OCR, receipt images, camera capture and chat attachments are not enabled. XLSX decompression protection is bounded primarily by the 10 MiB compressed input and parser behavior; hostile-workbook fuzzing and explicit expanded-size accounting should precede public deployment. Mapping profiles are saved server-side but the current UI does not yet provide a profile picker. Confirmed corrections continue through the normal transaction workflow rather than mutating import history.

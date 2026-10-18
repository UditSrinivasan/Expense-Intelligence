# Statement ingestion, receipts and categorization

## Pipeline

P0: `local select → browser validation → local parse → normalize → review → structured upload → server validation/deduplicate → atomic commit`

Every stage emits a versioned artifact and confidence/errors. Parser failures do not fall through to an LLM. Raw CSV/XLSX bytes are not uploaded. PDFs/images are P1 and either remain local or use a later explicitly approved temporary server path.

## File strategies

- **CSV:** browser detects encoding/delimiter; preserves raw row number; requires user-confirmed date convention when ambiguous.
- **XLSX:** browser worker reads cached values only, never executes formulae/macros/external links; visible sheet choice and strict sheet/row/cell limits.
- **PDF (P1):** browser text extraction for text PDFs with explicit accuracy limits. Complex/scanned tables require manual entry or an approved server parser; no silent claim of universal support.
- **Images/receipts (P1):** local preview and manual entry for real receipts. Free Gemini accepts only bundled/generated synthetic receipts in developer demo mode.

## India profiles and fixtures

Support profile contracts, not generic “all Indian banks” claims. First fixtures cover UPI merchant payments, person-to-person UPI transfers, IMPS/NEFT-style transfers, debit/card purchase, ATM, refund and fee. Normalize UPI references without assuming every `UPI` row is spending; counterparty, direction, reference pattern and user review determine type. Dates such as `01/02/2026` must never be guessed silently.

Receipt fixtures cover GST-inclusive/exclusive lines, CGST/SGST/IGST labels, service charges, discounts and rounding—but the product does not determine legal tax liability.

## UK profiles and fixtures

First fixtures cover debit/contactless card purchases, Faster Payments, bank transfers, standing orders, Direct Debits, cash withdrawal, refund and fee. Preserve statement-supplied transaction date and posting date separately. Receipt fixtures cover VAT-inclusive totals, multiple VAT rates, service charge, discounts and tips. Again, extraction labels what the receipt says; it does not issue tax advice.

## Normalized transaction candidate

Required: source row/page, raw description, parsed dates with convention/provenance, direction, exact amount/currency, candidate type, merchant/counterparty, reference, confidence and validation messages. The review UI shows raw alongside normalized fields.

## Deduplication

Exact provider/source ID wins. Otherwise create a fingerprint from owner/account, currency, absolute amount, direction, effective/posting date windows and normalized reference/merchant. A match is a suggestion, not silent deletion. Confirmed duplicate links remain auditable. Re-importing the same source hash is idempotent.

## Categorization ladder

1. Explicit transfer/refund/income semantics.
2. User rules with precedence and testable predicates.
3. User-scoped merchant aliases and prior confirmed corrections.
4. Versioned country-aware deterministic features.
5. Gemini structured classifier for ambiguous rows, with minimum context and no other users’ data.
6. Human review below calibrated threshold.

Never auto-create broad rules from one correction. Offer a preview such as “apply to future descriptions matching X,” and require confirmation. Measure precision/recall and calibration separately for India, UK, transaction type and category; unknown is a valid output.

## Receipt extraction and reconciliation

The extraction schema includes merchant, address (optional), dates, currency, items, quantity, unit price, line total, discount, tax lines, service charge, tip, rounding, final total, per-field confidence and evidence location. Deterministic reconciliation checks:

```text
sum(line totals) - item discounts - bill discount
+ taxes + service charge + tip + rounding adjustment = payable total
```

Do not infer whether tax is inclusive without evidence. Record the interpretation and alternative discrepancy. A configurable one-minor-unit tolerance may explain rounding but cannot silently edit a line. Commit requires a reconciled result or explicit user correction/acknowledgement.

## Initial quality gates

- Zero monetary sign/currency changes without review.
- ≥99.9% deterministic parser arithmetic correctness on synthetic fixtures.
- Per-profile field accuracy published only for tested profiles; target ≥98% amount/currency/date for supported CSV/XLSX profiles.
- Receipt payable-total exact-match ≥97% on the curated India and UK evaluation sets; uncertain fields are surfaced, not guessed.
- Categorization macro-F1 target ≥0.85 with no market below 0.80 before auto-suggestions; auto-apply disabled until calibration proves precision ≥0.95 per eligible class.

# UX-C receipt-to-split completion

## Delivered workflow

The group expense entry point is now a five-stage guided workflow: Details, People & Payers, Items & Splitting, Taxes & Charges, and Review & Confirm. It supports manual entry and browser-local PDF/JPG/PNG/WebP extraction through the existing PDF.js/Tesseract worker. File bytes and OCR text remain in the browser; only the corrected structured receipt is staged.

Uploaded receipts expose extraction confidence and require exact reconciliation. The user explicitly confirms provenance and may review a suggested bank-transaction match before linking it. A linked payment is recorded on the shared expense and excluded from consumption analytics so the bank debit and allocated shares are not counted twice.

Every item has editable quantity, unit price, line total, category, eligible consumers, and equal/quantity/percentage/exact/weighted/usage/time strategies. Bill-wide adjustments support proportional-to-item, equal, or custom-exact allocation with explicit eligibility. Inclusive tax stays in item prices; separate tax, discount, service, tip, and rounding rows reconcile as components.

Multiple payer contributions are independent from consumption. The confirmation preview comes from the existing deterministic largest-remainder backend and the confirmed record opens the existing expense-detail, obligation, copy, and share experience.

## Financial invariants

- Payer contributions, component totals, participant allocations, and balances must each reconcile in the currency's minor unit.
- Archived groups may preview history but cannot confirm a new expense or correction; enforcement is server-side and audited lifecycle state is preserved.
- A receipt can enrich at most one shared expense. Receipt owner, status, amount, currency, and date are revalidated during confirmation.
- Component categories drive each registered member's consumption analytics and budgets. Guests have no private dashboard rows.
- Linked bank purchases are excluded from consumption totals; allocated shares replace them. Settlements remain transfers and never become consumption.
- Cash paid and personal consumption remain separate in group balances and analytics.

## Database change

Migration `0011_receipt_split_attribution` adds receipt and bank-transaction provenance to `shared_expenses` and category attribution to `expense_components`. It supports an existing database at `0010` and the repository's current-metadata clean-install migration behavior. The complete PostgreSQL upgrade/downgrade/upgrade chain was exercised on a disposable database.

## Verification evidence

- SQLite: 83 passed, 4 PostgreSQL-only tests skipped.
- PostgreSQL 16: 87 passed, including concurrency, authorization, idempotency, rollback, and a five-person mixed-consumption receipt.
- Migration chain: clean upgrade to `0011`, downgrade to base, and clean re-upgrade to `0011` passed.
- Frontend unit tests: 8 passed.
- ESLint and Next.js production build passed.
- Playwright: desktop and Pixel 7 guided-flow checks passed; screenshots are generated under ignored `artifacts/ux-c/`.

The five-person acceptance fixture covers food/alcohol item assignment, an excluded participant for tax, a negative discount, service charge, two payers, deterministic rounding, receipt-to-bank linking, and owner consumption attribution of INR 429.18 instead of the INR 2,600 bank payment.

## Boundaries

Dietary data is not inferred or persisted. The proportional charge policy uses explicit item assignments as weights and leaves the backend as the sole final allocation authority. OCR still requires human review and no claim is made that every real-world receipt layout extracts perfectly. UX-D/E/F, deployment, and real-data external-model access remain out of scope.

# Final integration and deployment readiness

Verified: 25 October 2026. This is an engineering handoff, not authorization to change hosted infrastructure or deploy.

## Integrated baseline

- G2 PR #6 merged to `main` as `d3c7d718c4bded89b7cdc89ad0b8e77b670ab1e4` after its API and web checks passed.
- G2.1 PR #7 was retargeted from `feature/g2-cloud-deployment` to `main`, verified as one non-duplicated G2.1 commit, and merged as `217f937b6d9543e16aec87581af24f47f0ff07b8` after its checks passed.
- Migration order is linear from `0001_initial` through `0014_beta_refinement`. Hosted execution remains unapproved.

## Four-currency contract

INR, GBP, USD and EUR are first-class currencies. JPY and KWD remain supported where already implemented.

- Profiles accept all four home/display currencies; country remains an explicit India/UK choice and is never inferred from IP.
- Manual transactions, accounts, CSV/XLSX/PDF candidates and confirmed receipts preserve their original currency.
- Browser extraction recognizes `INR`/`₹`, `GBP`/`£`, `USD`/`$`, and `EUR`/`€`; uncertain documents still require editable review.
- Dashboards and analytics group totals by currency. They never add unlike denominations.
- Budgets convert only when a cached historical rate on or before the transaction date exists. Each contribution exposes provider, rate date and rate; unavailable conversions remain excluded and visible.
- Group expenses, components, percentage/fixed discounts, taxes, fees, allocations, balances and settlements reconcile within one expense currency using deterministic decimal minor-unit rounding. Balances stay separated by currency.
- Share text is generated from confirmed backend records and retains the recorded currency and state.
- UI formatting delegates symbols and separators to `Intl.NumberFormat`; stored decimal values remain locale-independent.

Valuation policy: original amounts and currency are immutable provenance. A converted view is derived from the latest available cached daily-reference rate whose date is not after the financial event. It is never described as real-time, and the app does not synthesize a missing rate.

## Original-document privacy boundary

| Path | Original location | Sent or persisted | Disposal |
|---|---|---|---|
| CSV/XLSX | Browser `File` and dedicated parser worker | API receives hash, filename, mapping and reviewed structured candidates only | worker is terminated and `File` state cleared immediately after successful staging |
| Text PDF | Browser `File`; PDF.js worker | API receives reviewed structured statement candidates or receipt candidate only | worker, preview URL, extracted text and `File` state are cleared after successful receipt confirmation; statement route navigation unmounts the source page |
| Scanned PDF/JPG/PNG/WebP | Browser worker; lazy local Tesseract data | same structured contract; no bytes or full OCR text | same cleanup as above |

The backend stage contracts reject unknown fields, so raw bytes, data URLs and extracted full text cannot be silently accepted. Database models contain provenance metadata and reviewed structured JSON/rows, not original blobs. There is no financial-document object-storage path. Application logs do not intentionally include request bodies.

Exception: a beta tester may explicitly attach a screenshot to a feedback report. That separate workflow warns against financial information and stores the user-selected screenshot; it is not an import path.

## Current free-tier boundary

- **Supabase Free:** two free projects per owner/admin allocation, 500 MB database-size quota per project, 50,000 monthly active users, and 5 GB uncached plus 5 GB cached egress. The fixed disk is 2 GB and can become read-only near capacity. Confirm the existing project and its dashboard usage immediately before migration. Sources: [billing](https://supabase.com/docs/guides/platform/billing-on-supabase), [database size](https://supabase.com/docs/guides/platform/database-size), [egress](https://supabase.com/docs/guides/platform/manage-your-usage/egress).
- **Netlify Free:** USD 0 with a hard 300-credit monthly limit and no auto recharge; reaching the limit pauses projects. One free team member and one concurrent build are included. Existing pre-September-2025 accounts may be on legacy pricing, so verify the account dashboard. Sources: [pricing](https://www.netlify.com/pricing/), [credit plans](https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/credit-based-pricing-plans/).
- **Northflank Developer Sandbox:** two services, two jobs and one add-on/database are advertised free and always-on, but Northflank says Sandbox is for testing rather than production and requires a payment method before resources can be created. This remains an explicit owner approval boundary. Sources: [pricing](https://northflank.com/pricing), [billing documentation](https://northflank.com/docs/v1/application/billing/pricing-on-northflank).

## Shortest deployment checklist

Already complete locally:

- PostgreSQL 16 and SQLite regression coverage, linear migrations through `0014`, authorization predicates/RLS scripts, bounded DB pools, hardened API image, hosted fail-closed configuration, same-origin API gateway, browser-local document processing and agent-disabled defaults.
- Four-currency preservation/separation and deterministic financial reconciliation tests.

Owner approval and account input required:

1. Approve the exact role/RLS/migration sequence in the G2 packet and confirm no real-data migration is included.
2. Confirm Supabase project Free status/usage and provide secret-safe owner, migrator and runtime connection access plus Google OAuth configuration.
3. Approve Netlify Free and connect the GitHub repository; provide the final frontend hostname.
4. Decide whether to accept Northflank's payment-method requirement and non-production Sandbox limitation. If not, select a reviewed backend host.
5. Supply the invited-user and feedback-admin email allowlists and final frontend/API origins.

Codex can execute after that approval: read-only hosted preflight, encrypted backup verification, role bootstrap, migrations through `0014`, RLS/grants, synthetic isolation checks, secret configuration through provider stores, deployment and synthetic browser smoke tests. It must stop on an unexpected schema, paid-plan prompt, changed provider terms, or any request to import real records.

Real-service checks still pending: Supabase dashboard quota/account metadata, real Google OAuth redirect, TLS/database connectivity, hosted RLS with pooled sessions, provider health/rollback, India/UK latency, invited-user browser sessions, and backup restoration against a disposable hosted target.

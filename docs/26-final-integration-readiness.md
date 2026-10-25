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
- **Blitz Free (conditional FastAPI candidate):** EUR 0, no card, no expiry and hard rather than billable limits; five apps share 512 MB reserved memory. It provides automatic HTTPS and a provider subdomain, Dockerfile/GitHub deployment, encrypted environment variables and gVisor isolation. Free apps sleep after 30 minutes, and documented programmatic requests do not wake them. The existing Netlify server gateway must therefore pass a real post-sleep wake test before selection. The provider is new, offers no SLA, stores app data in Germany/backups in Finland and uses Cloudflare TLS termination. Sources: [pricing](https://blitz.cloud/pricing/), [limits](https://blitz.cloud/docs/limits/), [deployment](https://blitz.cloud/docs/deploy-from-github/), [privacy](https://blitz.cloud/privacy/), [terms](https://blitz.cloud/terms/).
- **Rejected backend options:** Northflank and Koyeb require payment authorization; Back4app's current free container deployment lasts 60 minutes; Hugging Face requires a paid plan for Docker Spaces; Render's terms are unsuitable for this financial-data use; Railway/Fly/major clouds rely on billing, cards or expiring credits. None is an acceptable silent fallback.

## Shortest deployment checklist

Already complete locally:

- PostgreSQL 16 and SQLite regression coverage, linear migrations through `0014`, authorization predicates/RLS scripts, bounded DB pools, hardened API image, hosted fail-closed configuration, same-origin API gateway, browser-local document processing and agent-disabled defaults.
- Four-currency preservation/separation and deterministic financial reconciliation tests.
- The unchanged `Dockerfile.api` built and ran locally as `amd64`, honored an injected `PORT`, served health/readiness as a non-root user with the agent disabled, and used about 140 MiB idle memory. No hosted service was created.

Owner approval and account input required:

1. Approve the exact role/RLS/migration sequence in the G2 packet and confirm no real-data migration is included.
2. Confirm Supabase project Free status/usage and provide secret-safe owner, migrator and runtime connection access plus Google OAuth configuration.
3. Approve Netlify Free and connect the GitHub repository; provide the final frontend hostname.
4. Approve only a conditional Blitz Free account evaluation: no card/payment method/trial, passkey or TOTP enabled, DPA/subprocessors reviewed, and final provider subdomain recorded.
5. Supply the invited-user and feedback-admin email allowlists and final frontend/API origins.
6. Approve the synthetic Blitz checks in the G2 packet, including trusted-proxy verification and the mandatory post-sleep Netlify-gateway wake test. Failure means stop, not a direct-browser or weaker-security workaround.

Codex can execute after the relevant approval: verify account plan state, review downloadable account terms, configure provider secrets, deploy the existing container and perform synthetic browser/network smoke tests. Hosted backup, role bootstrap, migrations through `0014` and RLS/grants remain a distinct schema-change authorization. It must stop on an unexpected schema, payment prompt, missing trusted-proxy documentation, failed wake path, changed provider terms or any request to import real records.

Real-service checks still pending: Supabase and Netlify dashboard plan/usage, Blitz account/DPA/subprocessor and proxy metadata, the post-sleep server-gateway wake path, real Google OAuth redirect, TLS/database connectivity, hosted RLS with pooled sessions, provider health/rollback, India/UK latency, invited-user browser sessions, and backup restoration against a disposable hosted target.

If Blitz fails any zero-cost, privacy or wake-path condition, there is currently no verified architecture-preserving public FastAPI host meeting every constraint. The safe alternative is an owner-run local Docker instance reachable only through a private tunnel/VPN for the small demo, or postponing public access until a compliant free host exists. Supabase Free and Netlify Free can remain prepared without exposing the API or weakening authorization.

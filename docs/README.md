# Expense Intelligence planning pack

Status: **zero-cost showcase architecture proposed; implementation not approved**
Baseline date: **17 October 2026**
Launch markets: **India and the United Kingdom**

This directory is the pre-implementation specification. It contains no application code and creates no cloud resources.

## Decision summary

- Build a **modular monolith**: Next.js web/PWA, a minimal FastAPI API, and one PostgreSQL database. The ₹0 showcase has no continuously running worker; bounded work is request-scoped and durable long-running jobs remain disabled.
- Target ₹0 recurring cost with Vercel Hobby (personal/non-commercial web), Render Free (sleeping FastAPI), Supabase Free (PostgreSQL/Auth), and provider subdomains. These services have hard limits, suspension/pausing behavior and no application SLA.
- Treat PostgreSQL as the source of truth. Financial calculations use exact decimal arithmetic and immutable ledger-style records; the LLM never calculates or commits money.
- Keep private finance deterministic. The free Gemini API is limited to developer-run synthetic fixtures; the public app shows an honest recorded workflow replay because current terms require Paid Services for API clients available to UK users. No Gemini key is shipped to browsers.
- Use Frankfurter v2 daily rates as the primary zero-cost FX source, with cached provenance and an interchangeable provider contract. Rates are latest-available/historical references, never “real-time.”
- Parse CSV/XLSX locally in the browser where practical. Raw uploads remain local by default; any later server processing is temporary and opt-in.
- Do not launch publicly until India/UK counsel confirms notices, processor contracts, international-transfer mechanism, age position, retention schedule, and the exact DPDP provisions then in force.

## Deliverable map

| Requested deliverable | Document |
|---|---|
| PRD, personas, journeys, MVP acceptance criteria | [01-product.md](01-product.md) |
| Architecture, capacity, APIs, failure modes | [02-architecture.md](02-architecture.md) |
| Financial data model and entity relationships | [03-data-model.md](03-data-model.md) |
| Currency and FX subsystem | [04-currency-fx.md](04-currency-fx.md) |
| India/UK imports, receipt extraction, categorization | [05-ingestion-receipts.md](05-ingestion-receipts.md) |
| Expense splitting algorithms | [06-expense-splitting.md](06-expense-splitting.md) |
| Gemini/LangGraph, prompts, evaluation | [07-ai-system.md](07-ai-system.md) |
| Security, authentication, authorization, privacy | [08-security-privacy.md](08-security-privacy.md) |
| Offline sync and feature flags | [09-offline-flags.md](09-offline-flags.md) |
| UX system, screens, financial and admin dashboards | [10-ux-admin.md](10-ux-admin.md) |
| Free-tier comparison, deployment, cost, observability, CI/CD | [11-operations-cost.md](11-operations-cost.md) |
| Roadmap, ADRs, unresolved approvals | [12-roadmap-adrs.md](12-roadmap-adrs.md) |
| Local development and verification | [13-local-setup.md](13-local-setup.md) |
| Universal group splitting Milestone A | [16-universal-group-splitting.md](16-universal-group-splitting.md) |
| Settlements, templates and group intelligence Milestone B | [17-group-finance-milestone-b.md](17-group-finance-milestone-b.md) |
| Browser-local financial document ingestion Milestone C1 | [18-document-ingestion-c1.md](18-document-ingestion-c1.md) |
| PDF, OCR and receipt intelligence Milestone C2 | [19-pdf-ocr-receipts-c2.md](19-pdf-ocr-receipts-c2.md) |
| G1 hosted security foundation and approval gate | [23-g1-hosted-security-foundation.md](23-g1-hosted-security-foundation.md) |
| G2 deployment provider and hosted-change approval packet | [24-g2-deployment-approval.md](24-g2-deployment-approval.md) |
| G2.1 financial, appearance and beta-feedback refinement | [25-g2-1-prelaunch-refinement.md](25-g2-1-prelaunch-refinement.md) |
| Final integration, four-currency/privacy validation and deployment checklist | [26-final-integration-readiness.md](26-final-integration-readiness.md) |

## Non-goals for v1

Bank connectivity, UK Open Banking, Indian Account Aggregators, payment initiation, flight search, advertising, subscriptions, business accounting, payroll, invoicing, children’s accounts, and cross-device editing of shared balances while offline.

## Document authority

Product decisions supplied by the product owner override recommendations here. External prices, product capabilities, and laws are time-sensitive and must be revalidated before procurement or launch. This pack is engineering guidance, not legal, tax, accounting, or investment advice.

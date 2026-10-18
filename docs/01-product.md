# Product requirements

## Outcome and success criteria

Expense Intelligence helps adults in India and the UK understand private spending and settle shared costs without losing the original currency or handing arithmetic authority to AI.

Showcase targets:

- 1,000 registered users, 100 DAU, 20 concurrent active users.
- The earlier 5,000-documents/month and 99.5% availability targets are **superseded for the ₹0 showcase**. Free services may sleep, pause or suspend at quota; no availability SLA is promised.
- Warm p95 read API latency below 800 ms and write API below 1.2 s from the hosting region; the first request after Render idles may take about one minute. Measure London and Chennai separately.
- No cross-tenant disclosure; 100% of consequential AI proposals require confirmation.
- Financial invariant tests pass exactly; no binary floating-point in monetary paths.

## Personas

| Persona | Context | Primary jobs | Critical concern |
|---|---|---|---|
| Asha, India | INR, Asia/Kolkata, UPI and bank CSVs | categorize spending, budgets, receipt capture | UPI transfers must not appear as spending |
| Harshit, UK | GBP, Europe/London, cards, Faster Payments, Direct Debits | imports, subscriptions, shared costs | UK dates and payment types must parse correctly |
| Cross-border traveller | spends in INR/GBP/EUR | preserve original currency and see historical/display conversions | indicative rate must not masquerade as bank settlement rate |
| Group organizer | couples, flatmates or friends | itemize bills, invite users/guests, settle partially | private transactions remain private |
| Privacy-conscious user | either market | export/delete account and uploads | clear processing, retention and AI disclosures |
| Operations admin | aggregate operational role | diagnose failed jobs and costs | no routine access to raw financial data |

## Core journeys

1. **Onboard:** Google OIDC → verify server-side callback → accept current privacy/terms versions → set country, locale, home/display currency, time zone → empty dashboard.
2. **Import:** choose CSV/XLSX → browser validates and parses locally → review normalized rows and duplicates → send structured candidates only → confirm → atomic commit. PDF/image processing is P1, synthetic/local-only until a private processor is approved.
3. **Receipt and split:** capture/upload → extraction proposal with confidence → correct line items → choose payer/consumers/allocation → deterministic reconciliation → confirm → group ledger entries.
4. **Demo AI:** choose a bundled synthetic fixture → developer-only live Gemini graph or public recorded trace → typed tools/proposal/evaluation evidence. Real user data is structurally excluded.
5. **Local draft:** optional unsynchronized draft with explicit local/remote badge → reconnect → reauthenticate if needed → explicit upload and idempotent result.
6. **Leave:** export request → asynchronous archive → verify download → deletion confirmation → revoke sessions/OAuth linkage → deletion workflow and documented backup expiry.

## MVP features and acceptance criteria

| Priority | Feature | Acceptance criteria |
|---|---|---|
| P0 | Google login/onboarding | OIDC authorization-code flow; secure server session; adults-only attestation; revoked/expired sessions fail closed |
| P0 | Preferences | independent ISO country/currency, BCP 47 locale and IANA time zone; changing display currency never rewrites originals |
| P0 | Transactions | create/edit/delete with exact amounts; audit events; server ownership checks; refunds/transfers represented explicitly |
| P0 | CSV/XLSX imports | browser-local parse first; preview before upload/commit; only structured candidates sent; row errors isolated; duplicates surfaced |
| P0 | Categorization | deterministic rules first, AI only when ambiguous; confidence shown; correction creates user-scoped rule only with consent |
| P1 | PDF/receipts | local text extraction where reliable; synthetic Gemini demonstration; structured review and deterministic reconciliation |
| P0 | Groups/splits | registered and guest participants; payer independent of consumer; exact allocations; partial settlements; membership enforced server-side |
| P0 | FX/dashboard/budgets | original and display amounts labeled; rate type/source/as-of visible; cached/stale/unavailable states; India/UK locale tests |
| P1 | AI showcase | public recorded trace plus developer-only live free Gemini on synthetic fixtures; no private finance enters the model |
| P0 | Privacy | export and deletion workflows; raw upload deletion default; consent/notice version recorded |
| P0 | Operations | aggregate admin dashboard, audit trail, redacted observability, quotas, feature kill switches |
| Optional | Local mode | manual drafts and local-only demonstration data; no full offline promise; loss-on-browser-clear warning |
| Deferred | Banks, flights, ads, billing | interfaces/flags only where needed; no provider integration or speculative infrastructure |

## Product analytics

Collect only pseudonymous events needed for activation, import completion, correction rate, split completion, chat usefulness, deletion/export completion, latency and errors. Never put merchant descriptions, amounts, document text, prompts, emails, or group names in analytics properties.

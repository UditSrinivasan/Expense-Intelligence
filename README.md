# Expense Intelligence

A zero-cost-targeted, India/UK-compatible personal-finance showcase. It contains a Next.js interface, FastAPI API, and a bounded LangGraph finance assistant whose Gemini boundary accepts immutable synthetic showcase data only.

## Current status

- Works locally with development-only identity headers.
- Google/Supabase authentication integration is structurally supported but unconfigured.
- PostgreSQL is the target database; SQLite is supported only for quick local development/tests.
- Frankfurter is the configured daily-reference FX source. Network calls are not used in tests.
- The LangGraph agent exposes six typed, read-only tools for synthetic transactions, aggregation, comparisons, category breakdowns, fixed showcase FX and preferences.
- Authenticated read-only adapters for the real ledger cover transactions, merchants, category spending, budgets, analytics insights, recurring decisions, cached FX, authorized group balances, settlements and imports. They remain structurally disconnected from Gemini pending explicit private-processing approval.
- The deterministic finance API and `/transactions` interface now support hierarchical system/custom categories, exact reconciled allocations, parent rollups, explicit transaction types, and private opt-in merchant rules without Gemini.
- `/budgets` provides overall and hierarchical category budgets, monthly/custom periods, exact utilization, refund offsets, previous-period comparisons, cached historical FX provenance, missing-rate exclusions, drilldowns and immutable history without Gemini.
- `/imports` parses CSV and XLSX statements in a browser worker, supports manual column/date/number mapping, stages reviewed structured candidates, surfaces duplicates, and commits approved rows atomically with provenance. Raw statement bytes are not uploaded.
- `/documents` uses browser-local PDF.js and Tesseract.js workers for bounded PDF/image extraction, editable receipt reconciliation, conservative transaction linking and handoff to the universal split builder.
- The home dashboard provides currency-separated trends, category composition, shared-liability context, explainable anomaly evidence, recurring-series decisions, persisted feedback and adjustable sensitivity using a local deterministic rules engine.
- `CHAT_HISTORY`, `SHORT_TERM_MEMORY`, and `LONG_TERM_MEMORY` remain independent and default off. In local dev they can be toggled through authenticated `/v1/dev/flags/{name}` requests.
- Gemini stays disabled by default. Set `AGENT_MODE=synthetic_developer` only after confirming the API key's project plan; never send real financial or personal data through this mode.
- Deployment, payment initiation and remote document processing are not implemented.

## Agent safety boundary

The model cannot query the real ledger. Its registry closes over a separate immutable fixture, all tools label results `synthetic_demo`, graph recursion is capped, and no write/payment tool exists. Server code owns authentication and thread ownership. Free-tier Gemini content may be used by Google to improve products, so this mode is strictly a local synthetic showcase.

Enable history strategies independently in local development:

```powershell
Invoke-RestMethod -Method Put -Uri http://localhost:8000/v1/dev/flags/CHAT_HISTORY -Headers @{"X-Dev-User-Id"="00000000-0000-4000-8000-000000000001"} -ContentType application/json -Body '{"enabled":true}'
```

See [Local setup](docs/13-local-setup.md) and the [planning index](docs/README.md).

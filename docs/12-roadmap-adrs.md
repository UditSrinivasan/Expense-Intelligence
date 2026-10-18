# Roadmap, decisions and approvals

## Development milestones

The first deployment is shortened to a useful cross-border vertical slice. Estimates assume one developer using focused milestones; they are planning ranges, not commitments.

| Milestone | Duration | Exit evidence |
|---|---:|---|
| 0. Secure skeleton | 1–2 weeks | monorepo/CI, local PostgreSQL, shared money types, threat model, design tokens, provider config with no paid resources |
| 1. Deployed India/UK vertical slice | 3–4 weeks | Google login, preferences, manual INR/GBP transactions, dashboard, Frankfurter conversion, tenant tests, ₹0 deployment |
| 2. Local imports and budgets | 2–3 weeks | browser CSV/XLSX review, structured commit, categories, budgets, India/UK fixtures |
| 3. Groups and splitting | 3–4 weeks | registered users/guests, item allocations, cross-currency balances, settlements, concurrency/property tests |
| 4. Synthetic AI showcase | 2–3 weeks | developer-only live graph, public trace replay, prompt/evaluation/tracing UI, hard private-data gate |
| 5. P1 documents and hardening | 3–5 weeks | local PDF exploration, synthetic receipt extraction, admin aggregates, export/deletion, security/a11y/restore drills |

Expected first deployed slice: roughly 4–6 weeks. Broader showcase scope follows incrementally. Do not parallelize by splitting into microservices.

## Architectural decision records

### ADR-001: Modular monolith — Accepted

One repository, Next.js web, FastAPI modular API and PostgreSQL preserve boundaries and transactional consistency. The worker portion is deferred by ADR-006 for the ₹0 showcase. Split services only after measured scaling, ownership or isolation need.

### ADR-002: PostgreSQL is financial source of truth — Accepted

Exact numerics, transactions, locks and auditable relational constraints fit the ledger. IndexedDB and model state are caches/drafts only.

### ADR-003: Money is original-currency first — Accepted

Never overwrite original values. Conversions carry immutable provenance and explicit purpose. This enables cross-border correctness and reproducible reporting.

### ADR-004: Paid Gemini behind a model gateway — Superseded for showcase

The long-term choice remains valid, but ₹0 forbids it. ADR-013 defines the temporary synthetic-only mode.

### ADR-005: LangGraph only for bounded workflows — Accepted

Use state graphs for receipt/Q&A/proposal processes, not autonomous agents. Authorization and approval live outside model text.

### ADR-006: PostgreSQL outbox/job queue first — Superseded for showcase

Even a separate worker is unnecessary for P0. Retain this design for future long-running PDF/AI work after paid infrastructure is approved.

### ADR-007: Single-region managed beta — Superseded for showcase

Free-provider region availability constrains placement. ADR-014 defines the zero-cost topology; data-processing review still applies.

### ADR-008: CurrencyAPI primary, ECB fallback — Superseded for showcase

Valid paid option, but daily Frankfurter data meets PoC requirements at ₹0.

### ADR-013: Synthetic-only free Gemini — Accepted for showcase

Private Finance Mode has no LLM path. Developer-only Demo AI accepts immutable synthetic fixture IDs; public visitors see a labeled recorded trace. This meets privacy and current UK service-term constraints while preserving an inspectable LangGraph/evaluation portfolio artifact.

### ADR-014: Zero-cost hosted topology — Proposed

Use Vercel Hobby, one Render Free FastAPI service, and Supabase Free PostgreSQL/Auth, with no payment method where the provider permits. Accept cold starts, pausing, quota suspension and no SLA; fail closed rather than auto-upgrade.

### ADR-015: Browser-local structured import — Accepted for showcase

CSV/XLSX raw bytes stay in the browser; only reviewed structured candidates reach the API. PDF/images remain P1. This removes object storage and workers while reducing privacy exposure.

### ADR-016: Frankfurter daily FX — Accepted for showcase

Use its no-key public v2 blended feed with attribution and PostgreSQL caching. Preserve the provider abstraction and never call rates real-time.

### ADR-017: Online-first, optional local drafts — Accepted

Full offline sync is not justified. Local data is explicit, unsynchronized and disposable; shared/cross-device data remains remote.

### ADR-018: PostgreSQL-native memory subsystem — Accepted

Use owner-scoped chat tables, bounded checkpoints and explicit user-memory records in PostgreSQL. Start retrieval with typed filters and full-text search. Redis, a dedicated memory service, embeddings and pgvector are unjustified until evaluations show a retrieval gap.

### ADR-019: Independent memory feature flags — Accepted

`CHAT_HISTORY`, `SHORT_TERM_MEMORY` and `LONG_TERM_MEMORY` resolve independently. This supports controlled evaluations and permits long-term memory shutdown without disabling chat. Flags govern capability access, not authorization or deletion.

### ADR-009: Raw uploads deleted by default — Accepted

Retain through review/confirmation only, unless user explicitly opts in. This reduces breach impact; reprocessing then requires re-upload.

### ADR-010: No vector database in v1 — Accepted

Structured financial queries and bounded per-document context do not need semantic corpus retrieval. Revisit only with a measured retrieval requirement.

### ADR-011: Database-backed feature flags — Accepted

Typed flags, server enforcement and audit meet the initial requirement without another vendor.

### ADR-012: Guests are ledger participants, not accounts — Accepted

Guests have minimal identity and no authenticated access. A claim/invite flow is deferred until privacy and identity semantics are designed.

## Unresolved decisions requiring approval

1. Legal operator/controller entity and contact address in India/UK.
2. Approval of Vercel Hobby + Render Free + Supabase Free and acceptance of cold starts, pausing, quotas and no SLA.
3. Whether a public recorded AI trace satisfies the hosted showcase while live free Gemini stays developer-only. This is recommended under current UK terms.
4. Approval of Frankfurter daily blended rates for latest-available/historical PoC conversions.
5. Exact named Indian and UK bank/export profiles for the first compatibility promise. Recommendation: start with user-supplied redacted samples from two institutions per market plus a generic mapper.
6. Raw-file optional retention period and application-record inactivity policy. Recommendation: raw retained only by opt-in for 30 days initially; no arbitrary auto-deletion of confirmed ledger records.
7. Manual encrypted export/restore cadence for real showcase users; no RPO/RTO promise at ₹0.
8. Whether provider subdomains are acceptable; a custom domain is outside the guaranteed ₹0 plan.
9. Adult eligibility evidence: simple attestation versus date-of-birth collection. Recommendation: attestation without DOB unless counsel requires more, minimizing data.
10. Group deletion/departure semantics and the minimum audit data retained for other members. Recommendation: pseudonymize identity but preserve shared ledger integrity.
11. Showcase quotas and waitlist. Recommendation: invite-only, 20 local imports/user/month, no live end-user AI.
12. Whether to permit any real financial data before legal/provider review. Recommendation: begin with invited users, prominent showcase limitations and easy export/deletion.

## First implementation phase recommendation

Approved scope: implement Milestone 0 plus one local deployable path: Google-auth integration seam, India/UK preferences, one manual INR/GBP transaction, a minimal dashboard, one latest-available Frankfurter conversion, audit event, cross-tenant tests, and chat/memory schema/interfaces. Configure only local/free-capable components; do not provision cloud resources or implement the complete AI/chat workflow.

Do **not** start with dashboards, chatbot, receipt extraction or broad bank parsers. They depend on the identity, authorization, ledger, currency and provenance foundations.

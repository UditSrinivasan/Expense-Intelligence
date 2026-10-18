# Zero-cost deployment, provider limits and readiness

## Hosting comparison

| Option | Cost | Fit and limits | Decision |
|---|---:|---|---|
| Vercel Hobby + Render Free FastAPI + Supabase Free | ₹0 | preserves preferred stack; sleeping/pausing, quotas, no SLA, multiple processors | **Recommended showcase** |
| Vercel + Supabase only | ₹0 | fewer services, but replaces FastAPI/Python domain API with TypeScript/edge functions | reject for now; loses a core portfolio objective |
| Static/local-only app | ₹0 | strongest cost/privacy, but no shared groups or cross-device synchronization | useful demo mode, not the whole product |
| Paid managed deployment | >₹0 | workers, backups/PITR, private Gemini, reliability | future approved production path |

Vercel says Hobby is for personal, non-commercial use, matching the declared portfolio project while it remains non-commercial. Render Free supports Python/FastAPI, sleeps after 15 idle minutes, takes about one minute to wake, grants 750 instance-hours/workspace/month, has ephemeral disk, and suspends rather than charging when no payment method exists and limits are exceeded. Supabase Free currently includes two projects, 500 MB database/project, 1 GB storage, 5 GB egress, 50,000 MAU and 500,000 edge invocations; it may pause low-activity projects after seven days and can restrict/read-only service at quota. [Vercel pricing/plan purpose](https://vercel.com/pricing) [Render Free limits](https://render.com/docs/free) [Supabase Free quotas](https://supabase.com/docs/guides/platform/billing-on-supabase) [Supabase pausing](https://supabase.com/docs/guides/platform/free-project-pausing)

## Exactly what operates at ₹0

| Component | ₹0 implementation | Hard truth |
|---|---|---|
| Web | Vercel Hobby provider URL | personal/non-commercial only; quota/fair-use limits; no app SLA |
| API | one Render Free FastAPI service, no card | cold start; 750 hours; suspension at limits; no worker/private network |
| Auth/database | Supabase Free + Google provider | 500 MB DB; project can pause; quota restrictions; no PITR commitment |
| Files | browser memory only by default | refresh/navigation discards raw input; no persistent originals |
| Imports | local CSV/XLSX worker + structured sync | complex PDF/image parsing not P0 |
| FX | Frankfurter public v2 + DB cache | daily/non-live; public service/no SLA; abuse rate limiting |
| AI | developer-only free Gemini on synthetic fixtures; public trace replay | no live public UK Gemini at ₹0 under current terms |
| Jobs | request-scoped bounded work | no durable long-running processing |
| Monitoring | structured provider logs + aggregate DB tables | short retention/limited alerting; never sensitive content |
| Chat/memory | bounded PostgreSQL rows and full-text indexes | counts against 500 MB DB; no embeddings/vector service |
| Domain/email | provider subdomains; no email dependency | branded domain and transactional mail are optional costs |

Local development is also ₹0 using local PostgreSQL/container tooling and synthetic fixtures. The future paid deployment restores worker, object quarantine, paid/private Gemini, robust backups/PITR and an availability target.

## Cost and privacy blockers

- Public live Gemini for UK users requires Paid Services under current terms; free AI remains developer-only/synthetic.
- Persistent raw files, durable workers, automatic backups/PITR, SLA and reliable low-latency API cannot all be supplied at ₹0.
- Free providers can change terms/quotas or suspend service. Pin a verification date and recheck before deployment.
- A custom domain may cost money; provider subdomains preserve the zero-cost target.
- Free database capacity requires retention, aggregate rollups and operator alerts at 60/75/90%; financial records must never be silently deleted to recover quota.

Initial chat limits: 20 threads/user, 200 messages/thread, 8 KiB/message, 100 explicit memories/user, 4 KiB/memory, and at most 10 bounded checkpoints/thread with 30-day expiry. At maximum text payload this is roughly 32 MB per 20 fully populated threads/user before indexes/row overhead, so the theoretical cap cannot be offered broadly on a 500 MB database. Start invite-only with 25 messages/day/user, monitor actual bytes, and stop new chat persistence at an operator threshold rather than deleting ledger data. Store no raw attachments in message rows.

## Observability and feedback

OpenTelemetry-compatible request IDs join browser, API, provider and database activity where free tooling permits. Metrics: RED API metrics, cold starts, DB pool/query latency, import outcomes, parser profile success, synthetic model tokens/estimated paid-equivalent cost/errors, FX freshness, deletion/export status, auth failures and authorization denials. Logs use allowlisted structured fields and redaction; never raw document text, descriptions, values, prompts, tokens or credentials.

Track warm/cold latency, repeated authz denials, DB size, quotas, FX age, API wake failures and provider errors in aggregate tables plus free provider logs. Runbooks cover free-tier pause/suspension, bad parser release, suspected exposure, key rotation and manual restore. User feedback links pseudonymous IDs and warns against sensitive text.

## CI/CD and test pyramid

PR: format/lint/type checks, unit/property tests, API contract tests, migrations on ephemeral PostgreSQL, frontend component/a11y tests, Gitleaks, Semgrep and OSV/Trivy dependency scan. Add Checkov/Trivy IaC only when IaC/container files exist. Never interpret a passing scanner as security proof.

Trusted integration: Google/Supabase Auth stub and token-validation tests, browser parser corpus, cross-tenant authorization matrix, mutation idempotency and local/remote separation tests. Release candidate: synthetic AI evaluation, Playwright critical journeys, modest free-tier-safe load test, manual export/restore, migration/rollback rehearsal, deletion/export drill, DAST against authorized staging, SBOM and artifact provenance.

Local and hosted showcase environments use separate databases, OAuth clients and secrets where free-project quotas allow. CI uses short-lived credentials where available. Deployment requires protected approval, migration compatibility, health checks and previous-version rollback. Database rollback means forward fix/restore plan, never destructive down migration by reflex.

## Production gate

No showcase launch until: threat model reviewed; privacy notices identify free providers; tenant isolation and financial properties pass; parser matrix published; Gemini/FX/hosting terms revalidated; hard quotas and feature kill switches active; owner has exported/restored data; accessibility critical paths checked; and the UI honestly discloses cold starts/availability. Do not claim production readiness or 99.5% availability.

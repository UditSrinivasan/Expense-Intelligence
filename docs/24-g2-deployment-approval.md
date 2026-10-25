# G2 deployment approval packet

Status: **safe preparation and disposable rehearsal complete; no hosted schema, provider account, or deployment has been changed**.

Zero-cost addendum (25 October 2026): PRs #6 and #7 are integrated; migration `0014_beta_refinement`, its feedback-administration authorization, the additional RLS policies, the INR/GBP/USD/EUR contract and original-document privacy boundary are part of this approval. The deployment invariant is now **no charge, no card, no payment method, no paid trial and no automatic overage**. Provider limits were rechecked against first-party documentation on that date; account-specific plan state and usage must still be verified before any resource is created. See [the final readiness record](26-final-integration-readiness.md).

This is the single approval checkpoint for the reviewed hosted database sequence and the proposed providers. Approval does not authorize billing, destructive restores, importing existing private records, enabling AI, or broadening the invited-user list.

## Provider decision

### Recommended stack

| Component | Proposed provider | Cost boundary | Decision |
|---|---|---:|---|
| PostgreSQL and Google Auth | Supabase Free | USD 0 within Free limits | Existing project; acceptable subject to the reviewed database plan |
| Next.js | Netlify Free | USD 0, hard 300-credit monthly limit | Recommended; current policy says customer content is not used for AI training without explicit opt-in |
| FastAPI | DockHosting Free | USD 0; no payment method | Preferred candidate pending account, DPA, proxy and live cold-start verification |

Netlify supports Next.js App Router, SSR, route handlers, middleware/proxy, and OpenNext without an application rewrite. Its Free plan pauses at its hard monthly credit limit rather than charging automatically.

DockHosting Free documents three projects, up to 1 GB RAM per app, an HTTPS `*.dockhosting.dev` hostname, Dockerfile deployment and scale-to-zero with the first incoming HTTP request waiting for the container and then completing normally. Unlike Blitz, it does not classify a server-origin request as ineligible to wake the app, so it is compatible on paper with the existing browser -> Netlify gateway -> FastAPI path. It stores hosted content in Frankfurt, says it does not sell content or use it for AI training, and states that the Free plan requires no payment method. The application would use only one stateless container and Supabase PostgreSQL. Sources: [pricing](https://www.dockhosting.dev/), [Docker deployment](https://docs.dockhosting.dev/docs/deploying/docker), [scale to zero](https://docs.dockhosting.dev/docs/scale-to-zero), [privacy](https://www.dockhosting.dev/privacy), [terms](https://www.dockhosting.dev/tos).

Selection remains conditional because this provider is new, offers no uptime SLA, and its public material does not establish account MFA availability, a signed DPA/subprocessor list, trusted ingress proxy addresses or account-specific Free status. Those items and the real cold-start path must be verified before any private financial records are permitted.

### Rejected or conditional options

- **Render Free backend: rejected.** Render's current Terms prohibit transmitting or storing financial account information or similar personally identifiable financial information. This application processes bank statement and personal transaction data.
- **Vercel Hobby frontend: not selected.** It is personal/non-commercial only, and its current Terms permit customer-content model training on Hobby/trial Pro unless the account opts out. It remains conditional on explicit contract acceptance and verified opt-out.
- **Northflank and Koyeb: rejected.** Both conflict with the owner's explicit no-payment-method rule.
- **Blitz Free: rejected for this architecture.** Its rules say API clients and other programmatic requests cannot wake a sleeping app. The secure Netlify server gateway is such a request path; a direct browser visit to Blitz would not prove the application works and bypassing the gateway is prohibited.
- **FastAPI Cloud Hobby: conditional fallback only.** It advertises no-card Hobby hosting with 0.1 CPU/512 MB, HTTPS and encrypted secrets, but is a public beta, currently lists MFA/2FA as “Soon”, hosts data in the United States and has no reviewed DPA/subprocessor packet. It is not preferred for private finance traffic until those gaps close. Sources: [pricing](https://fastapicloud.com/pricing/), [secrets](https://fastapicloud.com/docs/builds-and-deployments/environment-variables/), [privacy](https://fastapicloud.com/legal/privacy-policy/).
- **Back4app Free containers: rejected.** Current first-party deployment guidance says a free container URL is destroyed after 60 minutes and must be redeployed; permanent hosting is paid. Sources: [pricing](https://www.back4app.com/pricing/container-as-a-service), [current deployment guide](https://www.back4app.com/blog/deploy-node-app-dockerfile-back4app).
- **Hugging Face Spaces: rejected.** Current documentation limits free accounts to static Spaces; Docker Spaces require a paid PRO or organization plan. Source: [Spaces overview](https://huggingface.co/docs/hub/spaces-overview).
- **Railway, Fly.io, Cloud Run and Oracle Cloud:** rejected because durable use depends on trial credits, billing activation or a payment card/account authorization.

The providers receive only the data necessary to run the application. Browser-local OCR keeps uploaded documents out of the backend by default. External LLM providers remain disconnected.

## Tested deployment configuration

- `Dockerfile.api` builds from a digest-pinned Python 3.12 slim image and the committed `uv.lock`, runs as UID 10001, binds the provider's `PORT`, and enables proxy handling only for `FORWARDED_ALLOW_IPS`.
- The API container passed `/health` and `/ready` checks with `AGENT_MODE=disabled`; the local container smoke used an explicit ephemeral SQLite path under `/tmp`, while hosted operation requires PostgreSQL.
- The provider-neutral local smoke used the existing image unchanged on `amd64`, listened on an injected `PORT=8080`, ran as the non-root `expense` user and consumed about 140 MiB at idle. That is below DockHosting's documented 1 GB Free ceiling; live memory behavior must still be checked without accepting a paid tier.
- PostgreSQL pools are bounded to five persistent connections plus two overflow connections and recycle after five minutes. Hosted startup rejects larger pools.
- Next.js fails closed in hosted mode unless its backend URL, Supabase URL, publishable key, and invite allowlist exist.
- Next.js emits CSP, frame, MIME-sniffing, referrer, and browser-permission headers and suppresses the framework header.
- The same-origin `/api/backend` route is the only browser-to-API gateway. It enforces origin checks, server-side session validation, a 30-second upstream deadline, and private/no-store responses.

## Exact hosted database plan

### Scope

Affected roles: `expense_migrator` and `expense_app` (new). Neither is superuser, `CREATEDB`, `CREATEROLE`, `INHERIT`, or `BYPASSRLS`. `expense_migrator` owns the 37 application tables; `expense_app` owns none.

Affected schemas: application objects in `public`; three helper functions in new schema `app_private`. Supabase-managed `auth`, `storage`, extensions, and platform roles are not changed.

Affected data: existing rows are not replaced or deleted. Alembic adds only migrations not already present, through `0014_beta_refinement`. Migration `0014` adds theme/accent preferences and optional private beta-feedback fields; it does not rewrite financial records. On an empty project the sequence creates the current application schema.

### Ordered execution after approval

1. Use the direct owner connection read-only to record `current_database()`, `server_version`, SSL state, current Alembic head, application table count, role flags, and project storage. Stop on an unexpected existing schema or incompatible version.
2. Confirm Supabase Free status and SSL enforcement. Export an owner-level logical backup, encrypt it with a new offline `age` recipient, record its SHA-256, and verify decryption before any DDL.
3. Run `supabase/role-bootstrap.sql` as the database owner. It creates the two restricted login roles, revokes public schema creation, gives only the migrator schema/database creation rights, and establishes default runtime grants.
4. Set strong random passwords for both roles in a secret-safe SQL session. Store them only in provider secret stores. Never place them in SQL files, shell history, GitHub, or screenshots.
5. Connect directly as `expense_migrator` with `sslmode=verify-full` and the Supabase CA. Run `alembic upgrade head`. Record the resulting head and table owners.
6. In one controlled migrator session, run `supabase/rls.sql`, followed by `supabase/application-role.sql`.
7. Verify `expense_app` flags are all false, table ownership is zero, expected table/function privileges exist, RLS (including `0014` feedback administration policies) is enabled, and an unscoped connection returns zero personal, group and feedback rows.
8. Configure the API runtime with the TLS Supavisor **session-mode** connection for `expense_app`, pool 5/overflow 2. Do not use the owner, migrator, Supabase service-role key, or transaction pooler initially.
9. Run synthetic two-user hosted tests: provisioning, independent INR/GBP/USD/EUR transactions, currency-separated analytics, historical-FX provenance, private groups, authorized shared group, pooled context reset, invite claim, exact financial reconciliation, feedback administration, logout, and denial after invite revocation. Send structured synthetic records only; do not upload original financial documents.
10. Only after those pass, configure the exact frontend/API HTTPS origins and Google/Supabase redirect allowlists, then invite the supplied real addresses.

### Disposable rehearsal result

The exact order above was rehearsed on PostgreSQL 16 in `g2_hosted_rehearsal`:

- both roles had all five privileged flags false;
- migrator owned 37 application tables and runtime owned zero;
- migrations reached `0013_group_invitations` during the original G2 rehearsal; `0014_beta_refinement` is validated separately before hosted execution;
- RLS and runtime grants applied successfully;
- runtime API provisioned two synthetic identities through RLS;
- user A saw one INR transaction and one GBP group; user B saw neither;
- a fresh unscoped runtime connection saw zero transactions and zero groups.

## Backup and rollback

`age` 1.3.2 is installed from the hash-verified Windows Package Manager package. Using PostgreSQL 16's `pg_dump`/`pg_restore` inside the project container, a custom-format synthetic dump was encrypted to a one-time `age` recipient, decrypted with an identical SHA-256, and restored into a separately named disposable database. The original restore reached `0013_group_invitations`, contained 37 public tables and the expected one synthetic transaction. G2.1 separately verified a clean PostgreSQL upgrade through `0014_beta_refinement`, downgrade to `0013_group_invitations`, and re-upgrade to `0014`; its disposable database was removed afterward. The disposable database, plaintext copies, encrypted copy, and one-time identity were then removed. The hosted pre-change backup is still pending because no hosted DDL is authorized yet.

Rollback before user traffic:

1. stop deployment or keep it disconnected;
2. revoke `expense_app` connection privilege and terminate only its sessions;
3. preserve the failed database for diagnosis;
4. restore the encrypted pre-change dump into a new disposable database or project;
5. validate migration head, row counts, financial reconciliation, and authorization before changing any connection target.

Do not overwrite the hosted database with a restore. If failure occurs after traffic begins, deploy the prior application release and revoke runtime access while deciding between a reviewed forward fix and a separately validated restore target.

## Required hosted secrets

Backend only:

- `APP_ENV=hosted`
- `DATABASE_URL` for `expense_app` using TLS session pooling
- `ALLOW_DEV_AUTH=false`
- `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE=authenticated`
- `WEB_ORIGIN=https://<frontend-host>`
- `INVITED_USER_EMAILS=<owner-supplied-list>`
- `FEEDBACK_ADMIN_EMAILS=<owner-supplied-reviewers>`
- `RATE_LIMIT_ENABLED=true`
- `DATABASE_POOL_SIZE=5`, `DATABASE_MAX_OVERFLOW=2`, `DATABASE_POOL_RECYCLE_SECONDS=300`
- `FORWARDED_ALLOW_IPS=<provider-proxy-cidrs>`
- `AGENT_MODE=disabled`, `MISTRAL_INFERENCE_ENABLED=false`

Frontend server/runtime:

- `APP_ENV=hosted`
- `API_URL=https://<api-host>` (server-only)
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `INVITED_USER_EMAILS=<same-owner-supplied-list>` (server-only)

No AI API key, database owner password, migrator password, Supabase service-role key, backup identity, or private document belongs in either deployment.

### Conditional DockHosting setup after approval

1. Create or verify a Free account without entering payment details, enabling a trial or accepting a paid plan. Enable MFA if the account offers it; stop if strong account authentication is unavailable.
2. Connect the GitHub repository and select the committed `Dockerfile.api` as the custom Dockerfile path. Do not use generated container configuration. Keep the provider-assigned HTTPS subdomain and the platform-provided `PORT`.
3. Configure only the backend variables above as secrets. Do not configure a DockHosting database, persistent volume or original-document storage.
4. Obtain documented ingress proxy addresses before expanding `FORWARDED_ALLOW_IPS`. Never use `*`; if trustworthy ranges are unavailable, stop rather than trusting spoofable forwarded headers.
5. Verify `/health` and `/ready`, Supabase TLS/session-pool connectivity, memory below the free ceiling, redacted logs, and synthetic authorization checks.
6. Determine the observed idle threshold, let the app sleep beyond it, then test the real browser -> Netlify `/api/backend` -> DockHosting route. The first request must wait, wake and complete safely while preserving the Supabase session.
7. Confirm the dashboard still says Free, exposes no payment method and offers no automatic charge path. Record the DPA/subprocessor, log-retention, MFA and provider-exit review.

Failure of any step leaves the API undeployed. The safe fallback is local Docker access over a private owner-controlled network for the invited demo, or waiting for a qualifying host; it is not a weaker authentication or direct-browser workaround.

## Approval required

Approval must explicitly cover:

1. the ordered hosted database/role/RLS plan above;
2. Netlify Free as the frontend provider under its current data policy;
3. conditional evaluation of DockHosting Free under the seven checks above, with no payment method and no paid fallback;
4. the DockHosting DPA, subprocessors, account-security controls and EU processing boundary after account review;
5. use of the owner-supplied invite addresses and exact provider-generated hosted URLs when allocated.

After that approval and the required account connections, only read-only/account checks and synthetic deployment validation may proceed. Hosted schema changes still require the separately stated database authorization. Any payment prompt, changed provider, destructive action, unexpected existing schema, broader data migration, failed wake-path test or weakened trust boundary requires an immediate stop and a new decision.

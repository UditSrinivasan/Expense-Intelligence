# G2 deployment approval packet

Status: **safe preparation and disposable rehearsal complete; no hosted schema, provider account, or deployment has been changed**.

Final integration addendum (25 October 2026): PRs #6 and #7 are integrated; migration `0014_beta_refinement`, its feedback-administration authorization, the additional RLS policies, the INR/GBP/USD/EUR contract and original-document privacy boundary are now part of this approval. See [the final readiness record](26-final-integration-readiness.md). Provider limits were rechecked against first-party documentation on that date; account-specific entitlement and usage must still be verified in each provider dashboard before any resource is created.

This is the single approval checkpoint for the reviewed hosted database sequence and the proposed providers. Approval does not authorize billing, destructive restores, importing existing private records, enabling AI, or broadening the invited-user list.

## Provider decision

### Recommended stack

| Component | Proposed provider | Cost boundary | Decision |
|---|---|---:|---|
| PostgreSQL and Google Auth | Supabase Free | USD 0 within Free limits | Existing project; acceptable subject to the reviewed database plan |
| Next.js | Netlify Free | USD 0, hard 300-credit monthly limit | Recommended; current policy says customer content is not used for AI training without explicit opt-in |
| FastAPI | Northflank Developer Sandbox | USD 0 for the included sandbox service | Recommended technical fit, but account/payment-method authorization and terms acceptance are required |

Netlify supports Next.js App Router, SSR, route handlers, middleware/proxy, and OpenNext without an application rewrite. Its Free plan pauses at its hard monthly credit limit rather than charging automatically.

Northflank provides two always-on sandbox services and container deployment, which fits the tested `Dockerfile.api`. Its documentation requires every account to add a payment method even on Sandbox. No account will be connected and no service will be created until the product owner accepts that external authorization and confirms the Sandbox plan. Billing must remain disabled beyond the included resources.

### Rejected or conditional options

- **Render Free backend: rejected.** Render's current Terms prohibit transmitting or storing financial account information or similar personally identifiable financial information. This application processes bank statement and personal transaction data.
- **Vercel Hobby frontend: not selected.** It is personal/non-commercial only, and its current Terms permit customer-content model training on Hobby/trial Pro unless the account opts out. It remains conditional on explicit contract acceptance and verified opt-out.
- **Koyeb Free backend: not selected.** It sleeps after one hour and its account flow requires a card with a USD 29 pre-authorization hold; this conflicts with the no-billing/no-charge boundary without separate approval.
- **Railway/Fly/major cloud serverless:** not zero-cost durable hosting under the current account assumptions, or requires billing activation.

The providers receive only the data necessary to run the application. Browser-local OCR keeps uploaded documents out of the backend by default. External LLM providers remain disconnected.

## Tested deployment configuration

- `Dockerfile.api` builds from a digest-pinned Python 3.12 slim image and the committed `uv.lock`, runs as UID 10001, binds the provider's `PORT`, and enables proxy handling only for `FORWARDED_ALLOW_IPS`.
- The API container passed `/health` and `/ready` checks with `AGENT_MODE=disabled`; the local container smoke used an explicit ephemeral SQLite path under `/tmp`, while hosted operation requires PostgreSQL.
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

## Approval required

Approval must explicitly cover:

1. the ordered hosted database/role/RLS plan above;
2. Netlify Free as the frontend provider under its current data policy;
3. Northflank Developer Sandbox as the backend provider, including its required payment-method authorization but no paid resources;
4. use of the owner-supplied invite addresses and exact hosted URLs when allocated.

After that single approval and the required account connections, routine execution of this exact plan can proceed without repeated confirmation. Any changed provider, paid resource, destructive action, unexpected existing hosted schema, or broader data migration requires a new decision.

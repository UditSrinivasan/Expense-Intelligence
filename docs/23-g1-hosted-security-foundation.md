# G1 hosted security foundation

Status: **local implementation complete; hosted changes are review-only and have not been applied**.

This plan is the approval gate for a controlled 4–5-person demo. Do not run the hosted SQL, migrations, restore commands, or deployment steps until the product owner approves this plan and supplies the exact project and deployment hostnames.

## Trust boundaries and invariants

- The browser authenticates through Supabase Authorization Code + PKCE. Session tokens remain in server-managed `HttpOnly`, `SameSite=Lax` cookies (`Secure` when hosted).
- Next.js performs navigation protection and same-origin CSRF checks. FastAPI independently validates every bearer JWT and performs all financial authorization; proxy checks are never the authorization boundary.
- Hosted access requires a Google identity whose normalized email is in the server-only `INVITED_USER_EMAILS` allowlist. Removing an email blocks its next request; Supabase session revocation should also be performed for immediate global logout.
- FastAPI uses a dedicated PostgreSQL role that is not an owner, superuser, or `BYPASSRLS`. SQLAlchemy ownership predicates remain required. RLS is defense in depth.
- Each database transaction receives `SET LOCAL` request identity. The session hook reapplies it after commit. A pooled connection without request context sees no personal or group data.
- External AI remains disabled (`AGENT_MODE=disabled`) and never receives real financial data. The finance product continues to work when an AI provider is absent.

## Reviewable hosted database change plan

Nothing in this section has been run against hosted Supabase.

1. In the Supabase dashboard, confirm the target project, Free plan, region, database size and PostgreSQL version. Record `show server_version;` and `show ssl;` output without recording credentials.
2. Enable **Enforce SSL on incoming connections** during a scheduled demo-maintenance window; Supabase documents that changing this setting restarts the database briefly. Download the project CA certificate and prefer `sslmode=verify-full&sslrootcert=<mounted-path>`; `sslmode=require` is the minimum accepted by application configuration.
3. Use the direct connection for Alembic, `pg_dump`, and restore. Use the Supavisor session pooler for the long-running FastAPI service unless a synthetic staging check proves transaction mode compatible with SQLAlchemy/psycopg, transaction-local context, row locks, and prepared statements. Keep SQLAlchemy's own pool small and enable pre-ping.
4. Take and verify an encrypted logical backup before schema changes.
5. As the database owner, run `alembic upgrade head` (through `0013_group_invitations`). Do not run migrations as the application role.
6. Review and run `supabase/rls.sql`, then `supabase/application-role.sql`. Set the `expense_app` password separately in a secret-safe SQL session; no password belongs in either file.
7. Point FastAPI's secret `DATABASE_URL` at `expense_app` with TLS. Confirm `rolsuper=false`, `rolcreaterole=false`, `rolcreatedb=false`, and `rolbypassrls=false`; confirm the role owns no application table.
8. Repeat the PostgreSQL RLS suite against a disposable/staging database using that role. Verify personal ownership and group membership separately, identity reset after pool reuse, commits, denials, invitation claim, and cross-user isolation.
9. Run a synthetic smoke journey. Inspect only redacted logs. Stop and roll back on authorization, reconciliation, or migration failure.

Rollback: stop application traffic; restore the prior application release; revert `DATABASE_URL`; run only the reviewed Alembic downgrade needed for `0013` after removing dependent invitation RLS policies, or restore the encrypted pre-change dump into a new disposable database and validate before any target switch. Never restore destructively over the hosted database during G1. Custom role passwords are not contained in Supabase backups and must be reset separately.

## OAuth and environment inventory

Google Console must authorize only Supabase's callback:

`https://<project-ref>.supabase.co/auth/v1/callback`

Supabase Auth URL configuration:

- local site: `http://localhost:3000`
- local redirect: `http://localhost:3000/auth/callback`
- hosted site: `https://<frontend-host>` (fill only after hostname allocation)
- hosted redirect: `https://<frontend-host>/auth/callback`

Server-only secrets/configuration: `DATABASE_URL`, `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, `INVITED_USER_EMAILS`, backup age identity/recipient, and any backend provider credentials. Browser-safe values are only `NEXT_PUBLIC_SUPABASE_URL` and the Supabase publishable key. Set `APP_ENV=hosted`, `ALLOW_DEV_AUTH=false`, `AGENT_MODE=disabled`, and `RATE_LIMIT_ENABLED=true`. Never put a service-role key in the web or API environment.

Set CORS to the exact HTTPS frontend origin. The browser calls the same-origin Next.js gateway; mutation requests require an exact same-origin `Origin`. Cookies must be secure, HTTP-only, scoped to the narrowest host/path supported, and never logged.

## Invitations and guest linking

The application allowlist controls entry to the product. Group invitations are separate, expiring, revocable, single-use bearer tokens. Only a group owner can create or revoke one. Only the authenticated account with the exact invited email can claim it. The server stores a SHA-256 token digest, not the token.

Claiming updates the existing guest `group_members` row instead of replacing it. Its identifier, historical expense allocations, settlements, balances, and display name therefore remain attached. The operation rejects an already-linked guest or duplicate membership. Guest participants are never treated as authenticated users before a successful claim.

## Rate limiting and observability

FastAPI applies instance-local fixed windows to general API traffic and tighter windows for agents, imports/receipts, group mutations, and feedback. Next.js limits auth initiation/callback/logout. Responses use HTTP 429 and `Retry-After`. Keys are one-way hashes and logs contain method, path, status, and elapsed time only.

These maps reset on restart and do not coordinate between instances. They are sufficient only for one small demo instance. Before multiple instances or a public launch, configure host/WAF edge limits for auth and expensive routes or add a shared limiter. Do not describe the in-process implementation as distributed abuse prevention.

## Backup, restore, retention and deletion

Supabase recommends off-site logical exports for Free projects; automatic daily backups are a paid-plan feature. Run `scripts/backup-postgres.ps1` with `pg_dump` and `age` before releases and at least weekly during the invited demo. Keep the `.age` file and checksum in private storage separate from the age identity. Retain four weekly copies unless the product owner approves a different legal retention schedule.

Quarterly and before the first demo, verify the checksum and restore with `scripts/restore-postgres.ps1` into a database whose name contains `restore`, `test`, or `disposable`. Run migrations/readiness, row counts, reconciliation, authorization, and synthetic login tests there. The script refuses other target names. Securely delete expired ciphertext and temporary plaintext. User deletion must revoke sessions/invites first, export if requested, then delete owned data according to documented product/legal policy; group ledger deletion needs group-owner/member rules and should not silently erase other members' accounting history.

Free tier has no recovery SLA. Weekly backups imply an RPO of up to seven days; actual RTO is unproven until an encrypted restore is timed on the chosen host.

## Hosting recommendation and limitations (verified 24 October 2026)

- Supabase Free currently advertises 500 MB database, 50,000 MAU, 5 GB egress, 1 GB storage, two active projects, and pause after one week of inactivity. It recommends manual off-site exports for Free projects.
- Render Free can host FastAPI but sleeps after 15 idle minutes and may take about a minute to wake. Its filesystem is ephemeral and free services are single-instance. Treat this as a demo constraint, not an SLA.
- Vercel Hobby is restricted by its terms to personal/non-commercial use. It is only suitable if this invited demo meets that condition; otherwise choose an eligible paid or alternative host.

Expected platform cost is USD 0 only while every selected account remains eligible for its free plan and below limits. No uptime, latency, backup, or continued-free-service guarantee exists. Configure spend controls/no payment method where supported and inspect account-specific usage before deployment.

## Approval checklist

- [ ] Product owner approves this hosted schema/role/RLS sequence.
- [ ] Exact Supabase project, PostgreSQL version, plan, region, and account-specific limits recorded.
- [ ] Exact frontend/API hosts chosen; Google and Supabase redirect URLs reviewed.
- [ ] Invite emails supplied through secret storage, not Git.
- [ ] CA certificate and application-role credentials stored as host secrets.
- [ ] Encrypted backup and timed disposable restore pass.
- [ ] Hosted/staging RLS and real Google account tests pass for India and UK invitees.
- [ ] Edge/global rate-limit choice documented.
- [ ] Retention/deletion owner and schedule approved.
- [ ] Provider terms and cold-start behavior accepted.

Only after every applicable item is checked should hosted changes or public deployment be separately authorized.

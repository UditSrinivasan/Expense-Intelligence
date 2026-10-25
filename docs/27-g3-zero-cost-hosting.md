# G3 zero-cost hosting validation

Verified from public provider documentation on 25 October 2026. This record does not authorize an external account, hosted schema change or public deployment.

## Decision

Use Supabase Free for PostgreSQL/Auth, Netlify Free for Next.js, and evaluate DockHosting Free for the existing FastAPI container. The invariant is zero cost, no payment method, no paid trial and no automatic charge. `AGENT_MODE` remains `disabled`.

Blitz is closed as a candidate for the current topology. Its Free service wakes only for a person opening the app in a browser and explicitly refuses to wake for API clients or programs. Netlify's authenticated same-origin route performs a server-side fetch to FastAPI, so an explicit browser visit to Blitz is not equivalent and no compliant configuration can make that route reliable after sleep.

DockHosting is the preferred live-test candidate because its Free documentation says any incoming HTTP request wakes the stopped container and the first request waits and completes normally. It accepts a custom Dockerfile, injects `PORT`, supplies a free HTTPS subdomain, allows up to 1 GB RAM and states that Free needs no payment method. Its privacy policy places hosted content in Frankfurt and says hosted content is neither sold nor used for AI training.

This is documentary verification, not account-specific proof. DockHosting is new and has no SLA. Public documents do not establish MFA availability, trusted ingress proxy ranges, a downloadable DPA/subprocessor list or the account's actual Free state. Private financial traffic remains prohibited until those are resolved.

## Existing configuration fit

No application rewrite is required. `Dockerfile.api` already builds a digest-pinned `amd64` image, runs as UID 10001, binds `0.0.0.0` to the injected `PORT`, exposes port 8000 and keeps application data in Supabase rather than the container filesystem. Local smoke validation passed `/health` and `/ready` with `AGENT_MODE=disabled` at about 140 MiB idle memory.

The DockHosting project must select `Dockerfile.api` as its Dockerfile path, attach no database or persistent volume, use only the provider-generated HTTPS hostname, and store the reviewed backend variables as secrets. `FORWARDED_ALLOW_IPS` must contain documented platform ingress ranges; never use `*`.

## Approval-gated live sequence

1. Owner authorizes creating/connecting a DockHosting Free account with no payment details or trial.
2. Verify dashboard plan state, absence of a payment method and absence of automatic billing; verify MFA/passkey/TOTP or stop.
3. Obtain/review the DPA, subprocessors, log retention and trusted proxy addresses. Stop if unavailable or unacceptable.
4. Deploy the current commit with synthetic configuration and Supabase access still withheld. Verify the container, HTTPS, redacted logs, memory and health behavior.
5. After separate hosted-database approval, configure the restricted `expense_app` TLS session-pool URL, JWT verification, exact origins and invite/admin allowlists. Never use owner, migrator or service-role credentials at runtime.
6. Test the browser -> Netlify `/api/backend` -> DockHosting path, record the actual idle threshold, wait beyond it, and repeat the first authenticated request. Confirm cold-start latency, request completion, session continuity and no credential exposure.
7. Run two synthetic accounts through INR/GBP/USD/EUR, import confirmation, discounts, payers, settlements, analytics, feedback and cross-user denial. Browser-local source documents must remain local.
8. Reconfirm all three dashboards remain Free before inviting users. A payment prompt, failed server-gateway wake, missing proxy assurance, security regression or quota surprise ends the deployment.

## Current evidence

- SQLite backend: 107 passed, 5 environment-specific skips.
- Clean PostgreSQL 16 migration through `0014_beta_refinement`: passed in a disposable database.
- PostgreSQL suite after migration: 112 passed; disposable database removed.
- Frontend unit tests: 18 passed; lint and production build passed.
- Playwright: 32 passed, 12 intentionally project-filtered skips. The run used local mocked/browser flows; it is not a hosted acceptance result.
- Gitleaks: no leaks found. No hosted resource or schema was changed.

## Fallbacks

FastAPI Cloud Hobby is technically compatible and no-card, with 512 MB and encrypted secrets, but it is public beta, U.S.-hosted, publicly lists MFA/2FA as “Soon”, and lacks a reviewed DPA/subprocessor packet. DockHosting alternatives with unclear ownership, HTTPS, data-processing contracts or account security are not suitable merely because they advertise free compute.

If DockHosting fails the approval gates, stop. The safe zero-cost fallback is an owner-operated local Docker instance exposed only through a reviewed private VPN/tunnel for the invited demo, or postponing public access. Do not bypass the Next.js gateway or weaken JWT, RLS or authorization.

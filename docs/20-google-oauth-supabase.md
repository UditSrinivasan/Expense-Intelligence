# Google OAuth and Supabase Auth

## Request boundary

The browser authenticates with Supabase through the Next.js server using Authorization Code + PKCE. Supabase access and refresh tokens are stored in `HttpOnly`, `SameSite=Lax` cookies (`Secure` in production), not local storage. Next.js Proxy verifies claims and refreshes the session. Client components call the same-origin `/api/backend/*` gateway; only that server route reads the session and forwards the access token to FastAPI.

FastAPI validates the JWT signature, issuer, audience, expiry, issued-at time and subject against the Supabase JWKS. Financial authorization remains in the existing SQLAlchemy ownership and group-membership predicates. `X-Dev-User-Id` is accepted only when both `APP_ENV` is `local` or `test` and `ALLOW_DEV_AUTH=true`; hosted settings cannot enable it.

Mutating gateway requests require an exact same-origin `Origin` header. OAuth redirect destinations accept relative paths only. Authenticated responses are marked private and non-cacheable.

## Dashboard setup required

1. Create or select a Supabase Free project. Do not add a payment method for this demo.
2. In Google Cloud Console, create an OAuth 2.0 Web application.
3. Add the callback URI shown by Supabase under **Authentication → Providers → Google** to Google's authorized redirect URIs. It has the form `https://<project-ref>.supabase.co/auth/v1/callback`.
4. Put the Google client ID and secret into the Supabase Google provider configuration. The Google secret belongs only in Supabase, never in this repository or the Next.js environment.
5. In **Authentication → URL Configuration**, set the local Site URL to `http://localhost:3000` and allow `http://localhost:3000/auth/callback`. Add the exact HTTPS hosted callback later, before deployment.
6. Copy the project URL and publishable key into the ignored local `.env` as `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
7. Set FastAPI's `SUPABASE_JWKS_URL` to `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` and `SUPABASE_JWT_ISSUER` to `https://<project-ref>.supabase.co/auth/v1`.
8. Set `APP_ENV=hosted` and `ALLOW_DEV_AUTH=false` for any non-development process. Keep `AGENT_MODE=disabled`.

No service-role key is used by this architecture.

## Row-level security status

FastAPI uses a pooled direct PostgreSQL connection, so `auth.uid()` is not populated automatically. The API sets transaction-local `app.auth_subject` and `app.current_user_id` values after JWT verification. `supabase/rls.sql` contains defense-in-depth policies based on that context.

Apply those policies only after creating a dedicated non-owner, non-`BYPASSRLS` FastAPI database role and granting it the required table/sequence privileges. A `postgres`, table-owner or service-role connection bypasses RLS and must not be used for ordinary hosted requests. The application ownership predicates remain mandatory even when RLS is enabled.

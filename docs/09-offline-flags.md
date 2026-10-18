# Offline behavior and feature flags

## Optional local scope

Full offline support is no longer an MVP requirement. The browser may use memory/IndexedDB for temporary document parsing, explicit local-only demonstration data and transaction drafts. Never use `localStorage` for session/authentication secrets or unprotected sensitive records. Never cache raw bank documents, receipt images, AI prompts/responses, exports, admin data or group settlement mutations.

Browser storage cannot guarantee secrecy on a compromised/shared unlocked device. Local data may disappear when site data or the browser profile is cleared. Every local object carries a `LOCAL ONLY — NOT SYNCED` badge; uploading requires an explicit action. Minimize fields and provide “Delete local data.”

## Synchronization protocol

- A draft receives client UUID, schema version, created-at, base record version (if any) and local status.
- On reconnect, refresh session/CSRF state; if reauthentication is required, keep the encrypted draft but do not upload until success.
- POST with idempotency key. A new manual transaction normally has no server conflict; duplicate fingerprint is returned for review.
- Server response is authoritative. Validation/authorization/conflict errors remain visible and retryable/editable; never report success before acknowledgment.
- Shared groups and cross-device personal records are remote-only in the showcase. They are never silently hydrated from local-only data.

Service worker upgrades use staged activation and schema migration; an incompatible cache is purged rather than misread. Storage pressure and quota failures produce a clear state.

## Feature flags

Define a typed registry for the named flags. Resolution order: emergency global off → environment default → market/cohort allowlist → user override. Server evaluates all security-relevant flags; the client receives only effective non-sensitive values. `ADVERTISEMENTS=false`, `BANK_CONNECTIONS=false`, and `FLIGHT_SEARCH=false` in every initial environment.

Each flag defines owner, description, type, default, environments, dependencies, expiry/review date and whether it is a kill switch. Changes require authenticated privileged actor, reason and append-only audit event. Production changes use two-person approval for privacy/financial/AI flags. Flags do not bypass authorization, schema migrations or data compatibility.

Add independent flags:

- `CHAT_HISTORY`: persistent threads/messages/search/feedback; default `false` until privacy UI and deletion tests pass.
- `SHORT_TERM_MEMORY`: bounded recent context, summaries and LangGraph checkpoints; default `false`, depends on an approved live AI mode but not on long-term memory.
- `LONG_TERM_MEMORY`: explicit remember/inspect/update/forget records; default `false`, independent of chat history and short-term memory.

Disabling a flag stops new reads/writes through that capability but does not silently delete data. Retention/deletion is a separate explicit operation. Emergency disable fails closed for memory retrieval.

Use a database-backed registry and short in-process cache initially; no external flag service is justified. Default closed when evaluation fails for risky features, while harmless presentation flags may use their compiled default.

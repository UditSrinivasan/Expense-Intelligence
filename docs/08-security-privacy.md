# Security, identity and regional privacy

## Trust boundaries and assets

Assets: identities/sessions, financial records, group ledgers, locally selected documents, structured imports, encryption keys, AI/FX credentials, audit logs and exports. Boundaries: browser-local parser↔untrusted files, browser↔web/API, API↔Supabase, developer-only synthetic AI↔Gemini, application↔Frankfurter, private user↔group, user↔admin, and hosted showcase↔CI/operator.

## Authentication and authorization

- Google OIDC authorization-code flow with PKCE/state/nonce and exact redirect URIs. Store issuer+subject as the stable identity, not email. Validate signature, issuer, audience, nonce and time claims server-side.
- Application session is opaque/rotatable in a Secure, HttpOnly cookie with idle and absolute expiry. Rotate on login/privilege change; support device listing/revocation and global logout.
- Every service method authorizes ownership or active group role. UI visibility and feature flags are not authorization.
- Policy matrix: users access own private resources; active group members access only group resources; guests have no authenticated access in v1; admins receive aggregate operations and pseudonymous job metadata, with exceptional support access excluded until a separately approved break-glass design exists.
- Background jobs reauthorize scope and deletion status at execution time. Exports use short-lived one-time downloads after step-up verification.

## Threat model

| Threat | Primary controls | Verification |
|---|---|---|
| IDOR/cross-tenant access | scoped repositories, opaque IDs, group/memory/thread ownership predicates, defense-in-depth RLS | negative matrix tests for every endpoint/tool/job |
| Session theft/login CSRF | OIDC checks, secure cookies, CSRF tokens/origin checks, rotation, revocation | auth integration tests |
| Malicious uploads | direct quarantine, MIME/signature/size/decompression limits, malware scan, sandboxed parsers, no outbound fetch | polyglot/bomb/macro corpus |
| SQL/XSS/CSRF/SSRF | parameterized ORM, output encoding/CSP, mutation CSRF, egress allowlist, no arbitrary URL tools | unit/integration tests and targeted scans |
| Prompt injection/exfiltration | free Gemini accepts immutable synthetic fixture IDs only; typed demo tools, bounded outputs, approval gate | adversarial evaluation suite and real-data canary rejection |
| Ledger tampering/races | exact decimals, database transactions/locks, idempotency, immutable audit/corrections | property and concurrency tests |
| Insider/admin exposure | least privilege, aggregate admin UI, redacted logs, production access audit | access review and canary records |
| Supply-chain/CI compromise | lockfiles, pinned actions/images, minimal tokens, protected environments, SBOM/scans | Gitleaks, OSV/Trivy, Semgrep; Checkov when IaC exists |
| Data remanence | lifecycle deletion, cache purge, backup schedule, processor deletion configuration | deletion drills |

OWASP ASVS is a requirements/checklist reference, not a certification. Critical exploitable findings block release; exceptions require owner, compensating control and expiry.

## Privacy architecture

Collect purpose-limited data, record notice/consent versions, separate optional analytics/AI processing from core service necessity, and make export/deletion accessible. Default raw-file lifecycle: quarantine ≤24 h if failed/abandoned; delete immediately after confirmed extraction/import; optional retention only by explicit user choice. Proposed application records remain until user deletion or account deletion; define exact inactivity periods with counsel/product before launch. Logs exclude content and expire on an operations schedule; AI trace bodies are off by default.

Chat history and memory are private user data. Search always includes the authenticated owner predicate; RLS mirrors it. Long-term memory is opt-in per record, visible/editable/deletable, carries provenance and optional expiry, and is never inferred silently from all messages. Account deletion covers messages, feedback, summaries, checkpoints and memories. Free-tier Gemini receives none of these records.

Backups are encrypted and expire on a documented rolling schedule (proposal: 35 days); deletion requests suppress restoration into active service, and any disaster restore replays the deletion tombstone list. Temporary exports expire within 24 hours.

## India assessment

India’s DPDP Act 2023 and notified DPDP Rules 2025 use phased commencement. The official Rules state that rules 1, 2 and 17–21 commenced on publication, rule 4 one year later, and rules 3, 5–16, 22 and 23 eighteen months later. Therefore implementation must maintain a dated obligation matrix rather than claiming one universal effective date. Notices, consent/legitimate-use analysis, rights/grievance handling, security safeguards, breach response, processor contracts and cross-border restrictions require India counsel review before public operation. [DPDP Act](https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023.pdf) [Notified DPDP Rules and timeline](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?pageTitle=Digit)

## UK assessment

Treat the operator as controller for the consumer service and vendors as processors where the facts support it. Establish Article 6 lawful bases by purpose, provide transparent notices, support data-subject rights, perform a DPIA before processing financial documents with AI, maintain processor agreements and breach procedures, and assess ICO registration/fee applicability. UK restricted transfers require adequacy, appropriate safeguards such as the IDTA/Addendum plus transfer risk assessment, or a narrowly applicable exception; user consent is not a blanket substitute. [ICO international transfer guide](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/a-guide-to-international-transfers/) [ICO safeguards](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/appropriate-safeguards/what-are-the-rules-on-appropriate-safeguards/)

## Residency recommendation

The ₹0 topology uses only regions offered by the selected free plans and therefore cannot promise ideal residency. Select the Supabase region only after India/UK DPA/subprocessor review and measure Render-to-database plus London/Chennai latency. This does **not** by itself satisfy either jurisdiction. Keep region configuration explicit so a paid regional migration remains possible. Real financial data never enters Gemini in the showcase; use paid regional/private controls later if approved. [Google Cloud data residency](https://cloud.google.com/terms/data-residency)

## Launch blockers

Before inviting real users: named legal owner; proportionate India/UK legal review; privacy/cookie notices; controller identity; free-provider DPAs/subprocessors and transfer assessment; data/breach request runbooks; adult-onboarding position; retention schedule; synthetic-only Gemini gate evidence; and tested deletion/export flows. A broader public launch still requires the fuller DPIA/compliance work previously described.

# Gemini, LangGraph, prompts and evaluation

## Boundary

AI extracts, classifies, explains and proposes. Deterministic services authorize, query, calculate, reconcile and mutate. Models receive no SQL/database credentials and cannot select arbitrary tables, users, files, URLs or tools.

The hosted ₹0 application has two hard modes:

- **Private Finance Mode:** deterministic rules, SQL analytics, exact financial services and no LLM calls. Real transactions, receipts, chat history, tool results and identifiers cannot enter an AI request path.
- **Demo AI Mode:** bundled synthetic fixtures only. Live free-tier Gemini is developer-only; public visitors see a clearly labeled recorded trace and evaluation results.

Google’s current terms say unpaid-service content may be used to improve products and may be reviewed by humans, warn against submitting sensitive/personal data, and require **Paid Services when API clients are made available to UK users**. They also state different data treatment for EEA/UK unpaid usage, but the Paid-Services availability rule still blocks a public free-tier UK client. Therefore UI consent or anonymization alone is insufficient. [Gemini Additional Terms, effective 23 March 2026](https://ai.google.dev/gemini-api/terms) [Gemini pricing/data-use table](https://ai.google.dev/gemini-api/docs/pricing)

The free model name and limits are configuration, not hardcoded. Google directs developers to view active rate limits in AI Studio, so the design does not invent a stable quota. The server applies a stricter developer quota, timeout and daily kill switch. No billing account or automatic paid upgrade is enabled without approval. [Official rate-limit guidance](https://ai.google.dev/gemini-api/docs/rate-limits)

## Provider abstraction

`ModelGateway.generate(WorkflowRequest) -> WorkflowResult` accepts a pinned provider/model, schema, timeout, token budget, safety settings and trace metadata. Provider adapters map errors into `timeout`, `rate_limited`, `invalid_output`, `safety_block`, `provider_unavailable`, or `policy_denied`.

## LangGraph workflows

Use one orchestrator graph per meaningful workflow, not multiple autonomous agents:

1. **Synthetic finance Q&A:** load server-owned fixture by ID → choose allowlisted demo tool → deterministic query/calculation → evidence check → response.
2. **Synthetic receipt:** load bundled fictional receipt → multimodal extract → schema validate → deterministic reconcile → user review.
3. **Categorize:** deterministic ladder → model only ambiguous batch → validate labels/confidence → threshold → review.
4. **Proposal:** create typed proposal → authorize affected resources → show diff → await external user confirmation → deterministic apply endpoint. The graph cannot confirm itself.

The live endpoint accepts fixture IDs, never arbitrary transaction/document payloads. Server looks up fixtures from an immutable allowlist and rejects free text, uploaded files, database record IDs and tool arguments that escape the fixture namespace. Graph state and traces contain synthetic IDs only. The Gemini key remains server-side. Retries: one schema repair and one transient retry.

## Tool contracts

Each tool has Pydantic input/output, required authorization scope, maximum result size, timeout, idempotency classification, audit policy and safe error shape. Examples: `search_transactions`, `aggregate_spending`, `get_budget_status`, `get_fx_rate`, `calculate_conversion`, `get_group_balance`, and proposal-only creators. Tool results carry evidence IDs the response can cite.

Document text and tool outputs are untrusted. Instructions inside statements/receipts are data. Model-selected identifiers are intersected with server-derived authorized scopes. Outbound URL fetching is absent from v1 AI tools.

## Prompt registry

Store reviewed prompt files in the future repository with metadata: `prompt_id`, semantic version, workflow schema version, owner, model allowlist, change rationale, evaluation run, approval and checksum. Traces record exact prompt/model/workflow versions. Prompt changes require evaluation evidence and staged flag rollout; rollback is configuration-only.

## Chat history and memory

- `CHAT_HISTORY` enables user-scoped threads, messages, titles, pagination/search, rename/delete, feedback and attachment references. It works without an LLM.
- `SHORT_TERM_MEMORY` enables bounded thread state only when a live, approved workflow is available. Retrieve a small recent-message window plus a versioned summary and relevant tool-result identifiers; authoritative values are re-queried. Checkpoints are user/thread scoped, expire, and never duplicate ledger rows.
- `LONG_TERM_MEMORY` enables explicit user-controlled memories. Initial retrieval uses type filters and PostgreSQL full-text search; no embeddings/pgvector. Remember/update/forget/inspect operations require explicit intent, validation, ownership checks and audit events.

The flags are independent: disabling long-term memory leaves history and the chatbot usable; disabling history prevents persistence but need not disable a stateless synthetic demo. In the ₹0 milestone all three schema/interfaces may exist, but live model consumption remains off.

Memory precedence is strict: ledger/budget/group services → current user settings → explicit long-term preferences → thread summary/recent messages. Memory never overrides financial facts. Forbidden memory includes secrets, tokens, credentials, raw documents and full payment identifiers.

## Evaluation sets and gates

Use synthetic/redacted, consented fixtures with separate India, UK and cross-border slices.

| Capability | Metric / beta gate |
|---|---|
| Receipt fields | exact/normalized field F1; critical amount/date/currency ≥0.95 per market |
| Reconciliation | deterministic invariant pass = 100% |
| Categorization | macro-F1 ≥0.85 overall, ≥0.80 each market; calibration error tracked |
| Tool selection | correct allowlisted tool ≥0.95; unauthorized invocation success = 0 |
| Grounded answers | cited claim support ≥0.95; numeric answers recompute exactly = 100% |
| Prompt injection | zero protected-data/tool-policy escapes in release suite |
| Proposal safety | confirmation bypass = 0; unauthorized target acceptance = 0 |
| Operations | p95 latency and cost per workflow within declared budgets |
| Follow-up resolution | synthetic referent accuracy by turn depth; no stale financial value reuse |
| Summarization | key intent/entity retention with forbidden-sensitive-copy rate = 0 |
| Long-term retrieval | relevance/precision, stale-memory warning and incorrect-memory avoidance |
| Isolation/deletion | cross-user retrieval success = 0; deleted/expired memory retrieval = 0 |
| Token efficiency | context tokens per successful follow-up versus full-history baseline |

Run deterministic/unit evaluations on every PR, a bounded model smoke set on trusted branches, and the full versioned suite before prompt/model release. Store scores, failure examples, model date/version and cost. Human review samples false positives and India/UK disparity. User feedback is linked to run ID without copying sensitive prompt text into analytics.

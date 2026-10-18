# Universal group splitting — Milestone A

An authenticated user can create a group, add guests, preview a split, confirm an immutable shared expense, and inspect exact balances by original currency. The group ledger is independent of private transactions; active membership authorizes group reads. Registered-user linking remains disabled until secure invitation acceptance is configured.

Payers and consumers are separate. Bills may contain multiple positive or negative components using `equal`, `percentage`, `exact`, `weighted`, `quantity`, `usage`, or `time`. The latter four are proportional inputs, not domain-specific subsystems. Strategies are recorded as `largest-remainder-v1`; expenses record `minor-units-v1`.

## Invariants

- Money uses `Decimal` and API amounts serialize as strings.
- Total, payer sum, and component sum match exactly in original currency.
- Every component reconciles in the currency's minor units.
- Every payer and consumer is an active group member.
- Per-currency balances sum to zero.
- Largest-remainder ties use stable member-ID order; unrounded values and residual recipients are persisted.
- Confirmation is retry-safe through a group-scoped idempotency key and database uniqueness constraint.
- Confirmed expenses are immutable in this milestone.

## Authorization

Active linked members can view a group and create or preview expenses. Only the owner can add members. Guests have no login identity and no private-finance access. Unauthorized group IDs return `404`. Mutations emit metadata-only audit events.

## API

- `POST /v1/groups`, `GET /v1/groups`, `GET /v1/groups/{id}`
- `POST /v1/groups/{id}/members`
- `POST /v1/groups/{id}/expenses/preview`
- `POST /v1/groups/{id}/expenses`
- `GET /v1/groups/{id}/balances`

## Deferred to Milestone B

Settlements, debt-edge suggestions, reusable templates, member removal, correction/reversal flows, group analytics, and cross-currency crystallization are deferred. Debts remain in each expense's original currency. No PG, rent, electricity, or property-management subsystem was created.

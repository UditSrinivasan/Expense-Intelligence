# Group finance — Milestone B

## Settlements and balances

Settlements record repayments completed or agreed outside Expense Intelligence; no money is transferred. Confirmed payments adjust derived balances as `paid - consumed + settled out - settled in`. Pending entries do not affect balances. Reversals preserve the original record, mark it reversed, and add a linked reversal record.

The service rejects self-payment, foreign group participants, invalid minor units, stale group versions, duplicate idempotency keys, and amounts above the current payer-to-payee obligation. Group-row locking plus optimistic versions serialize competing mutations. Former members remain in calculations until their balances reach zero.

The debt simplifier greedily matches the largest debtors and creditors per currency. It preserves every net balance, does not rewrite history, and is presented only as a recommendation; it does not claim a mathematically minimal transfer count.

## Templates and corrections

Templates store a group, name, currency, optional category, validated component definitions, participant inputs, allocation strategy, and version. Applying one produces a new editable draft with a fresh idempotency key. Updating a template never changes confirmed expenses.

Correction preview removes the original expense's net effect and adds the proposed replacement effect. Confirmation marks the original reversed and creates a linked replacement atomically. Creator or owner authorization is required. The conservative v1 policy blocks correction while the same currency has confirmed settlements; users must reverse those settlements first.

## Analytics and currencies

Group analytics expose original-currency totals, categorized totals, timelines, paid-versus-consumed values, current balances, settlement counts, recent/largest expenses, and unsettled suggestions. Reversed expenses are excluded once and replacement expenses included once. Independent currencies are never merged.

Cross-currency settlement and FX crystallization remain deferred. Display data is exact by original currency; no indicative conversion is represented as payable debt.

## API additions

- `GET/POST /v1/groups/{id}/settlements`
- `POST /v1/groups/{id}/settlements/{settlement_id}/confirm`
- `POST /v1/groups/{id}/settlements/{settlement_id}/reverse`
- `GET /v1/groups/{id}/debt-suggestions`
- `GET/POST /v1/groups/{id}/templates`
- `PUT /v1/groups/{id}/templates/{template_id}`
- `POST /v1/groups/{id}/templates/{template_id}/apply`
- `POST /v1/groups/{id}/expenses/{expense_id}/correction-preview`
- `POST /v1/groups/{id}/expenses/{expense_id}/correct`
- `GET /v1/groups/{id}/members/all`
- `PUT /v1/groups/{id}/members/{member_id}`
- `GET /v1/groups/{id}/analytics`

## Known limits

Live registered-user invitations remain disabled until an authenticated, expiring acceptance channel is configured. There is no payment initiation, automatic recurrence, background scheduling, cross-currency settlement agreement, or claim that simplified transfers are mathematically minimal.

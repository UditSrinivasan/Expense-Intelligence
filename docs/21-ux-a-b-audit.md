# UX-A/B audit and staged plan

## Findings before implementation

1. Navigation was route-specific, incomplete, and inconsistent. Account controls floated over page content and nested routes depended on browser Back.
2. `/groups` mixed group discovery, participant management, and a 7-strategy expert expense form. The primary task—opening an existing group—was visually secondary.
3. Workspace sections were incomplete and not reflected in the URL. Expenses and group settings had no dedicated destinations.
4. Member controls existed, but adding a guest was separated from member management. Group rename and reversible archive operations had no API contract.
5. Permanent deletion is unsafe: the current database relationships would cascade through confirmed expenses and shared history. A UI-only delete would also be an authorization failure.
6. Empty, loading, and error messaging existed, but each page presented it differently. Mobile navigation was horizontal overflow rather than a coherent application menu.

## Information architecture

- Overview
- Transactions
- Budgets
- Groups
  - Directory
  - Group workspace: Overview, Expenses, Balances & Settle, Templates, Members, Settings
  - New Expense (existing deterministic builder; UX-C will replace its interaction design)
  - Expense details and sharing
- Insights (dashboard anchor until the dashboard stage creates a dedicated view)
- Imports & Documents
- Assistant
- Settings

## Implemented in UX-A/B

- One authenticated desktop/sidebar and mobile/menu shell with active routes, account actions, skip link, focus states, and breadcrumbs.
- A group-first directory with active and archived groups, member/currency summaries, outstanding totals, activity, create-group disclosure, and direct actions.
- A dedicated `/groups/new-expense` route preserving the existing calculation workflow.
- Complete workspace navigation plus explicit Back to Groups and Back to Group links.
- Owner-authorized rename, archive, and restore operations with optimistic version checks and audit events.
- Member management and guest addition in one workspace section.
- No destructive group deletion. Archive preserves confirmed expenses, balances, settlements, members, and audit history.

## Planned UX-C contracts

The guided builder will reuse the existing preview/confirmation API and browser-local PDF.js/Tesseract pipeline. Its staged state must represent receipt evidence, editable items, payer contributions, component allocation strategies, charge eligibility, reconciliation status, and an idempotency key. React will collect intent and render backend previews; it will not become a second money engine.

Before UX-C is complete, backend attribution must prove that participant consumption—not merchant payment or later settlement—drives personal analytics, budgets, categories, and anomalies. Linked bank transactions and receipts must remain one economic event. Draft persistence is deferred until an authenticated, owner-scoped server contract exists; session storage is not a durable financial draft system.

The interactive product tour remains UX-F work after stable route and builder targets exist. It must store completion/dismissal per user and use only non-persistent illustrative data.

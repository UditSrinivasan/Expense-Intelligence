# Deterministic budget management

Budgets are owner-scoped application records and never depend on Gemini.

## Periods and scope

- Monthly budgets must cover an exact local calendar month.
- Custom budgets accept inclusive start and end dates.
- The user's IANA time zone is stored with the budget. Transactions already carry a local financial `effective_date`, so daylight-saving transitions do not change which local date is included.
- A null category means overall purchase spending. Category budgets include the selected category and all descendants.
- Overall budgets include uncategorized eligible transactions; categorized and mixed transactions are still counted exactly once.
- Parent and child budgets are evaluated independently. The API never sums overlapping budgets into a portfolio total.

## Spending policy

- Only current allocations for purchase expenses and refunds contribute.
- Refund allocations subtract from spending; transfers and account movements are excluded.
- Mixed-category allocations retain the original payment and count each allocation once.
- Same-currency amounts remain exact. Cross-currency allocations use the latest cached daily-reference rate on or before the transaction date.
- Missing historical rates are reported by source currency and excluded from the displayed spend. No network fetch occurs during budget evaluation.
- Display quantization follows the budget currency: JPY uses zero decimals, KWD uses three, and supported INR/GBP/USD/EUR budgets use two.

## Lifecycle and safety

- Create, edit, archive/restore and soft delete are supported.
- Every state change creates an immutable revision and audit event.
- Updates and deletes require the expected version; stale writes return HTTP 409.
- Reads and mutations enforce server-side owner predicates and return the same not-found response for absent or foreign records.

# Categories and private classification learning

The first deterministic categorization slice is implemented independently of Gemini.

## Implemented

- Stable parent/child categories with global defaults and owner-scoped custom categories.
- Versioned custom-category create/read/update; system categories cannot be edited by users.
- Separate transaction type, raw description, normalized description, merchant, classification source, confidence and review state.
- Exact, Unicode-normalized merchant aliases. No broad merchant-name regex classification.
- User-approved exact merchant rules with owner isolation, precedence, disable/enable and deletion.
- Manual single-category and mixed-category allocations that must exactly reconcile to the original payment.
- Historical allocation rows are retained; corrections mark the old rows non-current rather than rewriting them.
- Parent category rollups use current allocations and exclude transfers and non-purchase movements.
- Audit events for category, categorization and rule mutations.
- Direct `/transactions` UI for search, correction, custom-category creation and rule review.
- Atomic bulk correction with a separate preview step, per-currency totals and explicit confirmation.

## Intentionally deferred

- Category-alias management, rule-scope editing and exception lists.
- Statement import and receipt-line capture.
- Groups, bill splitting and settlements.
- Agent access to real finance services. The existing Gemini path remains synthetic-only.

These are separate vertical slices so they can reuse the reconciled allocation and category services without duplicating money logic.

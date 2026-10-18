# UX, dashboards and design system

## Product character

Calm, precise and editorial rather than decorative: dense enough for financial work, generous enough on mobile, with a warm neutral canvas, near-black text, one restrained indigo action color, green/red reserved for semantic outcomes, and no gradients/glass/glow. Converted values are visually secondary to originals.

## Tokens

- Typography: Inter Variable (fallback system sans) for UI; tabular numerals for money; 14 px body on dense desktop, 16 px inputs/body on mobile; headings 20/24/32 px.
- Spacing: 4 px base; 8/12/16/24/32/48 scale. Radius 8 px controls, 12 px surfaces; pills only for compact statuses.
- Color targets: canvas `#F7F6F3`, surface `#FFFFFF`, text `#181817`, muted `#6B6A66`, border `#DDDAD3`, action `#3F51B5`; final palette must pass WCAG contrast in rendered testing.
- Motion: 120–220 ms for state continuity; none for decoration; honor reduced motion.
- Focus: visible 2 px high-contrast ring with offset. Touch targets ≥44×44 CSS px.

## Navigation and screen hierarchy

Desktop side rail / mobile bottom navigation: Overview, Transactions, Groups, Budgets, Assistant; Imports and Settings live in contextual/top menus. Primary screens:

1. Onboarding and regional preferences.
2. Overview: cash-flow summary, budget progress, category trend, group balance, recent activity, sync/import status.
3. Transactions: searchable virtualized table/list with filters and original/display amount pair.
4. Import review: source row beside normalized candidate, issues first, bulk actions reversible.
5. Receipt review/split builder: image/document evidence, editable items, reconciliation bar, payer and consumers.
6. Group: balances, expenses, settlements, members and currency policy.
7. Budgets: period-aware utilization and comparison explanation.
8. Assistant: conversation, citations, actual tool activity, approval cards and failure recovery.
9. Privacy/settings: sessions, exports, deletion, retained documents, AI/privacy choices.
10. Admin: aggregate product/operations only.

On mobile, tables become disclosure rows, receipt capture is a first-class action, and the split builder uses a step flow rather than a compressed matrix. Desktop may show a resizable evidence pane. Full-bleed mobile controls respect safe-area insets; gesture interactions always have tap and keyboard alternatives.

## Financial visualization rules

Default to bars/lines over pies; no 3D. Axes, period, currency and conversion policy are always labeled. Do not mix currencies on one quantitative axis unless converted by a single stated policy. Tooltips show original value, converted value, rate source/type/as-of. Missing data creates gaps, not zeroes. Comparison reports freeze the rate policy for reproducibility.

## States and accessibility

Every view defines loading/skeleton, empty, permission denied, partial/stale, validation error, system error, offline, success and destructive confirmation states. Use semantic HTML, labels and descriptions, keyboard navigation, live regions for job changes, 200% zoom support, non-color status cues, and locale-aware screen-reader money text. Ambiguous numeric dates display month names in review screens. Search, filters, date ranges, tabs and pagination live in the URL so views are restorable and shareable without encoding sensitive values. Forms preserve paste, warn before discarding edits, focus the first invalid field, and provide actionable errors.

AI UI shows observable phases (“checking transactions”, “calculating conversion”), elapsed time, cancel/retry, evidence and redacted expandable tool details—not chain-of-thought. Proposals show a deterministic before/after diff and separate Confirm button.

## Component architecture

Use shadcn/ui/Radix primitives selectively. Compose domain components (`Money`, `FxProvenance`, `ImportIssue`, `ReconciliationSummary`, `ApprovalCard`) rather than accumulating boolean props. Providers expose state/actions/meta interfaces; heavy charts, spreadsheet preview and document viewer load dynamically. Lists above 50 visible rows are virtualized. Server components own initial reads; independent data fetches run in parallel; client boundaries receive minimal serialized data. Use `Intl.NumberFormat` and `Intl.DateTimeFormat`; locale comes from user preference/browser negotiation, never IP inference.

## Admin specification

Admin overview contains registrations, DAU/MAU, retention cohorts, feature adoption, uploads by status/market, AI calls/cost/latency, import failures by parser profile, API/job health, queue age, storage and deletion SLA. Drilldowns use pseudonymous IDs and safe error codes. No merchant descriptions, transaction amounts, prompts, document previews, private group details or arbitrary user impersonation.

Before UI acceptance, run keyboard/axe checks and inspect responsive rendered states with Playwright. Playwright is discoverable in the current environment, but no UI exists to validate yet.

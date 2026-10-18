# Expense-splitting specification

## Model and invariants

Payers and consumers are independent. An expense has one original currency and exact total; multiple payers may fund it. Items/charges are allocated to participants, including guests. The following must always hold in original currency:

```text
sum(payer amounts) = expense total
sum(allocation amounts) = expense total
for each item/charge: sum(allocated shares) = item/charge amount
participant balance = paid - owed - net settlements
sum(all participant balances) = 0
```

Tax allocation follows the receipt’s monetary structure and configured allocation policy; excluding a participant from a charge is an allocation choice, not a tax exemption statement.

## Allocation algorithms

All algorithms operate in integer minor units at the allocation boundary.

- **Equal:** `q, r = divmod(total_minor, n)`; each gets `q`, with one residual unit assigned in stable participant-ID order starting after the last residual recipient for repeated allocations.
- **Percent:** validate percentages total exactly 100 at accepted precision; compute unrounded decimals, floor to minor units, then allocate residual units by largest remainder with stable ID tie-break.
- **Weights/proportional:** same largest-remainder method using positive weights.
- **Custom:** exact minor-unit amounts must sum to total; reject otherwise.
- **Shared item:** run the chosen algorithm within the selected consumer set.

Store algorithm/version, inputs, unrounded shares, rounded shares and residual recipients. Property tests cover conservation, permutation/tie behavior, negative/refund expenses, zero-minor currencies and three-minor currencies.

## Debt and settlement

Balances are canonical; “who owes whom” is a presentation/settlement suggestion. A deterministic greedy simplifier matches the largest debtor and creditor until balances reach zero. This reduces transfers but does not promise the mathematical minimum number of edges. Existing real-world debts are not rewritten when display simplification changes.

Settlement records are immutable after completion; corrections use reversal/replacement. Partial settlement reduces the relevant balance. Concurrent completion takes a row lock and checks aggregate/version plus idempotency key.

## Cross-currency policy

Debt remains denominated in the expense’s original currency unless participants explicitly agree to crystallize it in another currency. Display conversions are indicative and never change debt. A settlement in another currency records:

- original debt amount/currency;
- settlement amount/currency;
- agreed rate or actual processor/bank outcome;
- fees/spread separately;
- agreement timestamp and approving participants;
- residual debt and rounding disposition.

The group may choose `PER_EXPENSE_ORIGINAL` (recommended default) or an explicit group settlement policy. Policy changes affect future expenses only unless every affected member confirms a migration.

## Authorization

Members can view group records during active membership. Only permitted roles create/invite/remove; expense creators or managers may edit drafts; finalized expense changes require an auditable correction flow. Guest records contain minimal identity data and confer no login or private-data access. Removing a member cannot erase balances needed by remaining members without an explicit settlement/correction.

# Milestone D evaluation

## Scope and accounting policy

The dashboard is deterministic and user-scoped. Purchases count once, refunds reduce spend, income excludes refunds, and transfers, account movements and card repayments are excluded. Current category allocations replace (rather than add to) the transaction category. Shared-expense liability is reported separately from personal cash flow. Currencies remain separate; the analytics endpoint performs no implicit FX conversion.

## Synthetic India/UK evaluation

Run on 18 October 2026 with `pytest -q` using `tests/test_analytics.py`:

| Dataset signal | Expected | Detected | False positives |
| --- | ---: | ---: | ---: |
| India unusual amount | 1 | 1 | 0 |
| India exact near-time duplicate | 1 | 1 | 0 |
| UK monthly recurring rent | 1 | 1 | 0 |

For the two anomaly labels, precision was **100% (2/2)**, recall was **100% (2/2)**, and the observed false-positive count was **0**. The recurring evaluator found **1/1** deliberately stable series. These are small controlled fixtures, not a claim about real-world accuracy. Sparse ledgers explicitly return `history.unusual_amount: false` instead of manufacturing an alert.

## Thresholds and evidence

- Unusual amount: at least six prior same-currency purchases; threshold is the historical median plus the larger of one median or a sensitivity-adjusted median absolute deviation.
- Possible duplicate: exact normalized merchant, amount and currency within one day.
- Recurring suggestion: at least three observations, weekly (6–8 days) or monthly (25–35 days), with amounts within 20% of their median.
- Every insight stores its algorithm version, reporting period and supporting transaction IDs. Recomputing expires stale insights while preserving feedback and dismissals for stable fingerprints.

## UI validation

The production build and lint passed. Browser QA passed at 1280×desktop and 390×844 mobile viewports with accessible headings, labels, status output, responsive single-column fallback and no failed application request. The empty state was used for this rendering check; populated behavior is covered by API integration tests.

## Known limits

The rules deliberately favor precision over recall. Merchant/category frequency shifts and statistical seasonality are not inferred yet. Group liability is gross confirmed consumption for the selected period, while settlement balances remain on the group screens. There is no cross-currency roll-up unless a future view can display a cached rate and its provenance beside every converted value.

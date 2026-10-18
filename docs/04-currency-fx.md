# Currency and FX subsystem

## Recommendation

Use a replaceable `FxProvider` interface. For the ₹0 showcase, select **Frankfurter v2 blended rates** as primary. Its official site states that the public API needs no key, covers 223 currencies from official sources, provides daily/historical data, allows caching and commercial use of blended rates, and has no monthly/daily quota (abuse rate limiting still applies). [Frankfurter documentation and terms summary](https://frankfurter.dev/)

Use provider attribution expansion and cache each required INR/GBP/USD/EUR observation in PostgreSQL. Frankfurter rates are daily reference/mid-market data, not live transaction quotes and carry no application SLA. The earlier CurrencyAPI Small choice is superseded solely by the zero-cost constraint; retain it as a future commercial option. ECB direct-provider queries are optional for audit comparison and remain subject to ECB information-only terms. [ECB usage terms](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html)

## Contract

```text
get_latest(base, quotes) -> RateSet
get_historical(date, base, quotes) -> RateSet | Unavailable
health() -> ProviderHealth

RateSet = provider + rate_type + base + {quote: Decimal} +
          observed_at + published_at + fetched_at + attribution + raw_hash
```

Adapters validate positive finite decimals, known ISO codes, timestamp bounds and required quotes. Cross rates derive deterministically through the provider base and record both source rates. Never combine rates from providers in one conversion.

## Semantics

- `LATEST_INDICATIVE`: freshest provider publication, never “live” unless the contract truly supplies live market data.
- `HISTORICAL_INDICATIVE`: provider value associated with an effective date.
- `ACTUAL_SETTLEMENT`: user/imported bank value including disclosed fees/spread; provider rates cannot create it.
- `AGREED_GROUP_RATE`: explicit participant agreement, immutable after affected settlement confirmation.

Transaction-time reporting selects the latest historical rate whose provider date is on/before the transaction’s local effective date, subject to a configured lookback for weekends/holidays. Store the chosen rate ID for reproducibility. “Current value” uses the latest rate and is clearly labeled separately.

## Currency registry and rounding

Seed a versioned ISO 4217 registry rather than code constants. It includes alphabetic/numeric code, minor units, active dates and display metadata. Initial verified behavior covers INR, GBP, USD, EUR, AED, JPY, CAD, AUD and SGD; zero- and three-minor-unit test currencies are mandatory.

Keep calculations at high precision. Round only at a named boundary: user display, import acceptance, item allocation, settlement, or export. Allocation residual units are assigned deterministically as specified in [06-expense-splitting.md](06-expense-splitting.md).

## Caching and outage policy

- Store provider snapshots permanently when referenced by a financial record; cache latest snapshots at least until the next expected working-day publication.
- Fetch on first demand per currency/date under a database lock; subsequent users reuse the cached observation. Do not add a paid scheduler.
- UI labels: source, rate type, effective/as-of time, fetched time, and `fresh`, `delayed`, `stale`, or `unavailable`.
- Suggested thresholds: latest is fresh ≤2 hours for hourly provider, delayed ≤26 hours, stale thereafter. ECB working-day data uses a calendar-aware policy.
- Offline conversion is permitted only from a synchronized cached rate and displays its age. Missing rates produce an unavailable state.

## Cost-display conversion

Planning estimates use **£1 = ₹130.20**, derived from ECB 16 October 2026 reference values `EUR/INR 109.8650` and `EUR/GBP 0.84385` (`109.8650 / 0.84385`). It is an indicative planning conversion, not a purchase quote. [ECB 16 October 2026 table](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)

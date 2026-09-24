# Historical Data Contract

Minimum daily input:

ticker, date, open, high, low, close, volume

Recommended historical level fields:

close_raw

Use close/open/high/low for split-normalized technical structure. Use close_raw (as-traded historical close) for absolute price-level rules such as Kell's $10 floor. If close_raw/raw_close is absent, v0.1 marks the historical price-floor result unknown rather than applying the rule to a back-adjusted level.

Volume should represent the historical shares traded on that date; document any vendor volume adjustments.

Benchmark input:

date, close

Technical price data should be split-normalized so moving averages and patterns remain continuous across splits. Do not use back-adjusted historical levels for absolute dollar-price gates. Dividend adjustment policy must be documented.

## Point-in-time requirements

For a snapshot dated t:
- price/volume features may use bars <= t only;
- weekly context may not use later sessions from the same week;
- universe membership should be point-in-time where possible;
- fundamentals require observation/publication timestamps before inclusion;
- serious historical tests should include delisted stocks to reduce survivorship bias.

## Provenance

Record dataset version, price source, benchmark, universe source, universe-as-of method, adjustment method, code commit and known survivorship limitations.

Do not commit large proprietary/raw datasets. Commit schemas, small fixtures, reproducible code and aggregate reports.

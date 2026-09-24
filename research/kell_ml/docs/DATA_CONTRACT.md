# Historical Data Contract

Minimum daily input:

ticker, date, open, high, low, close, volume

Benchmark input:

date, close

Price data should be split-adjusted.

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

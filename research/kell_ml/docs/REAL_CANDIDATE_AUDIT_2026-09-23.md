# Real candidate/chart sanity audit — 2026-09-23

Purpose: regression-check the research-only Kell ML logic against real StockScout chart data. This is **not** historical model validation and **not** a trading recommendation.

## Inputs

- Source: existing Review Grid / Kell chart snapshot, first shard only.
- Snapshot session: 2026-09-23.
- Symbols audited: 48.
- Daily history per symbol: generally 260 sessions.
- Benchmark: QQQ daily bars through 2026-09-23.
- Important source-format finding: some chart dates are ISO strings while others are Unix-second timestamps.

## Structural proxy distribution

- REPAIR_OR_OTHER: 22
- EMA_CROSSBACK_PROXY: 13
- WEDGE_POP_PROXY: 7
- BASE_N_BREAK_PROXY: 5
- EXHAUSTION_EXTENSION_PROXY: 1

This initially looked too permissive because several Crossback structures had weak relative strength. The correct fix was **not** to rewrite their structural stage. Kell's framework separates structural location from stock/setup quality.

## Separate review-bucket result

Applying the transparent research review layer to the same 48 symbols:

- PRIORITY_REVIEW: 4
- STRUCTURE_ONLY: 18
- WATCH: 22
- PRICE_INELIGIBLE: 3
- EXTENDED: 1

Current-price context is safe for the 2026-09-23 row; historical absolute price-floor use requires raw/as-traded close.

### PRIORITY_REVIEW proxy cases

| Ticker | Structural proxy | 20D RS vs QQQ | RVOL20 | Avg volume 20D |
|---|---|---:|---:|---:|
| WDC | EMA_CROSSBACK_PROXY | +0.8% | 0.78 | 6.42M |
| ALNY | WEDGE_POP_PROXY | +0.2% | 0.90 | 1.62M |
| SFNC | WEDGE_POP_PROXY | -3.7% | 1.63 | 1.30M |
| DBRG | BASE_N_BREAK_PROXY | -4.2% | 1.66 | 4.73M |

The latter two qualify via unusual-volume confirmation rather than positive 20D RS. This is a project proxy and should be challenged during Gold calibration.

### Under-$10 current-price cases

- KODK — $9.66
- SXC — $9.95
- YEXT — $6.44

Their structural labels are retained, but Kell's stated under-$10 avoidance makes them current name-selection rejects.

## Bugs/design issues caught

1. Mixed ISO/Unix date encodings would break naive pandas date parsing. Fixed with explicit Unix-second normalization.
2. Stage and setup/selection quality were initially too easy to conflate. Fixed by keeping silver_stage and review_bucket_proxy separate.
3. Historical absolute price levels can leak future split information when back-adjusted data are used. Fixed by requiring close_raw/raw_close for the historical $10 gate; otherwise the gate is unknown.
4. Forward outcome columns remain excluded from all structural feature contracts and from blind Gold queues.

## Interpretation

This audit demonstrates integration correctness and useful selectivity on real data. It does **not** demonstrate predictive edge. Predictive claims require a survivorship-aware historical panel, blind Gold labels, and walk-forward evaluation.

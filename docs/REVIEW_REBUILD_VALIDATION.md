# Review Lab rebuild validation

## Baseline and data corrections

The pinned production baseline is `82b12be589828a6e114d5c4ac8635aacaa52787c` with EOD data through 17 November 2026. The rebuild advances in [draft PR #76](https://github.com/Garrincha077/StockScout-Trend-Birth/pull/76).

| Check | Before | Rebuild |
|---|---:|---:|
| Kell five-session coverage on the same 48 archived sessions | 60,731 / 90,120 | 75,756 / 90,120 |
| EMBJ 5D across the 4:1 ADS split | −77.0909% | −8.3636% |
| Confirmed stage transitions through 17 November | 10,692 | 10,019, using adjacent exchange sessions |

Kell measures from the next open with complete exchange windows. The stage replay values registered corporate actions in as-published quotes and remains a separate archive. The source-verified ledger covers the actions identified in the November audit. A spin-off requires the exit quote for both holdings. The historical paths and original outcome shards remain available for comparison.

## Kell swing view

The first pass separates setup structure from the old rank. It requires an observable price pivot and discloses the planned stop, maximum entry, gap and state. The close can confirm a pivot. Any simulated execution uses a later session. The $5 price floor, $5m trailing dollar-volume filter, maximum stop fraction of 8% and maximum chase of 0.5R are explicit project parameters.

Replay uses 39 contemporaneously archived signal sessions within 48 total. The chart store comes from the pinned production baseline and may exclude symbols absent on that last day. On dates where the swing rule selects candidates, each alternative selects the same count, up to five, from names with the same price/liquidity gate and trailing 63-session momentum coverage. Comparison uses next-session open and equally weighted signal dates. The separate limit/stop illustration applies the new plan's price bounds and estimates the range allowed by the available daily bars.

| Hold | Paired dates | Plans per strategy | Kell swing | Prior readiness/score | 63-session momentum |
|---|---:|---:|---:|---:|---:|
| 5 sessions | 34 | 170 | +0.197% | −0.081% | −0.521% |
| 10 sessions | 29 | 145 | +1.133% | +0.367% | −4.450% |
| 20 sessions | 19 | 95 | +2.791% | +2.543% | −11.533% |

Table uses 20 bp round-trip cost. At 50 bp subtract 0.30 percentage points from each row. For the five-session stop/limit simulation, 117 selected plans fill. Average net R ranges from +0.102 to +0.217 at 20 bp and −0.036 to +0.079 at 50 bp. This is an exploratory short-period comparison with overlapping holdings, historical OHLC uncertainty, partial corporate-action coverage and an assumed publication before the order window. The matching date comparison measures rank selection before a per-plan trigger constraint.

To reproduce from the pinned score-history and chart directories:

```sh
python scripts/replay_kell_swing.py \
  --scores-dir lab/data/kell-score-history \
  --charts-dir lab/data/kell-charts \
  --as-of 2026-11-17 --output kell-swing-replay.json
```

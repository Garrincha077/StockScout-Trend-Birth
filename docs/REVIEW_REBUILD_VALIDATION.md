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

## Early Trend Birth

The independent early model looks for repair near a 41-session support region following at least a 15% decline from the preceding structural high. It requires recovering price and two corroborating observations, including a level-based observation. The card shows price evidence, 20-session performance relative to SPY, support, invalidation and the reclaim pivot. Confirmed candidates have cleared their pivot and reached stage 3 or higher in the daily or weekly model. The daily EOD archive preserves the early selection and the comparison shortlist before any outcome can mature.

The retrospective replay covers 36 dated observations from 25 September to 17 November. The common symbol-day universe reconstructs 73,932 of 94,861 archived eligible symbol-days and retains 504 of 540 weekly selections. Later charts were sliced at each observed signal date. This reconstruction still carries survivorship, missing-data and retroactive adjustment risk. Early alerts preceded daily 4/4 in 24 of 38 joint first entries, were tied in 4, and came later in 10. The median signed lead was 6 sessions. No early/weekly entry pair shared a ticker in this window.

| 20 sessions | Early Trend Birth | Daily 4/4 | Weekly base |
|---|---:|---:|---:|
| Observed / matured | 122 / 130 | 310 / 323 | 12 / 12 |
| Signal dates with returns | 12 | 12 | 2 |
| Top-decile observations | 10 | 29 | 1 |
| Non-leader observations | 112 | 281 | 11 |
| Below same-date median | 57 | 200 | 4 |
| Top-decile opportunities missed (of 2,413) | 2,403 | 2,384 | 2,412 |
| Average excess over same-date median | +0.880 pp | −4.236 pp | +6.473 pp |

The study pairs each event with its own date's closing-price universe. The weekly average rests on two dates and cannot establish an advantage. The early shortlist has 282 first alerts pending at each of the 63-, 126- and 252-session horizons. Those horizons are tested with synthetic maturation and await genuine elapsed sessions.

To reproduce, use the pinned Review full snapshot and the matching monthly stage/close and dated weekly archives. In the source directory, name the independent file copies `trend-birth-ticker-history_YYYY-MM.json`, `trend-birth-price-history_YYYY-MM.json` and `weekly-birth-shadow_YYYY-MM-DD.json`.

```sh
python scripts/replay_early_trend_birth.py \
  --snapshot pinned-review.json \
  --sha256 c781974749de559e63af09e61700bd67433bd0eab072275208a7ec39795e2adc \
  --archive-dir archive-inputs --output early-replay.json
```

## Migration and rollback

1. Record the live Vercel deployment, the active `publication.json` snapshot ID and the Git SHA of `feature/unified-review-grid-lab`. Retain the first dated links and one exact snapshot URL as smoke-test inputs.
2. After owner approval, review and merge PR #76 into the existing Review Lab deployment branch. The next ordinary publication stages Review, charts, research, alerts and Watchlist together. Check the run ID, session date and Unified hash across the pointer and companions. Verify the quote and chart gates, then open Statistics and the PWA on a signed-in Android device.
3. Release the controller separately through [PR #77](https://github.com/Garrincha077/StockScout-Trend-Birth/pull/77) into `main`. Compare the controller log, activated Unified manifest and downstream publisher attempt. The controller is a GitHub workflow change.
4. For UI rollback, restore the prior approved Vercel deployment and submit a Git revert on the Review Lab branch. For a data rollback, pause publication and alerts, restore the prior verified pointer and its matching moving reports in one reviewed commit, then validate timestamps and absolute archive links before resuming. Preserve the content-addressed archives for both versions. Watchlist storage keeps the existing keys and ownership model throughout.

The staged preview uses an isolated build with exact November 17 data. The latest forward archive has one genuine observation of the new model. The retrospective cohort study and live maturation are recorded separately. Owner sign-in needs an Android smoke test on the production origin after release approval.

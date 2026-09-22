# Oliver Kell Overlay Scoring v2 — PDF grounded

Branch scope: `feature/kell-mcp-lab`

This layer scans the **deduplicated union of all candidates already published by StockScout Unified** across Bottom, Next and Ryan. It does not create a new market-wide universe and does not alter Unified candidate generation, source ranks, or the ordinary Review Grid.

The model is `kell-overlay-v2-pdf`. It was revised against Oliver Kell's *Victory in Stock Trading*. The book supplies the qualitative framework; where Kell does not publish a numerical threshold, this lab uses an explicit, reproducible proxy and labels it as such.

## Source hierarchy

1. Existing Unified candidate membership.
2. Existing Unified daily OHLCV/chart history.
3. Unified embedded relative-strength series (`RS = stock / SPY * 100`) to reconstruct point-in-time SPY history.
4. Existing Unified context fields such as `rsRank`, `fundamentalSupport`, `revenueYoY`, and `epsYoY`.
5. No external symbol may be added to the candidate pool by the Kell layer.

## Name-selection context

- `kell_name_selection_ok`: price >= $10 and prior 20-session average volume >= 1,000,000 shares.
- `kell_growth_context`: if both revenue YoY and EPS YoY exist, both must be >=25%; if only one numeric field exists, it must be >=25%; `fundamentalSupport` is used only when neither numeric growth field is available.
- `kell_rs_leader`: Unified RS rank >=90.
- `kell_weekly_trend_ok`: weekly close is at/above a rising 10-week EMA.

These are transparent research proxies around the book's name-selection framework, not claims that Kell published these exact scanner formulas.

## Momentum, volume and gaps

| Screen | v2 operational definition |
| --- | --- |
| 52W / New High | Close within 3% of 52-week high or current bar makes a new 52-week high |
| Unusual Volume | RVOL20 >=2.0x |
| RVOL 3x | RVOL20 >=3.0x; separate screen flag |
| Bull Snort | RVOL20 >=2.0x, bullish/positive response, close in top 30% of daily range |
| 3M +50% | 63-session return >=+50% |
| 6M Doubler | 126-session return >=+100%; this is the true `kell_doubler` compatibility flag |
| Gapper | Opening gap >=+3% |
| Buyable Gap proxy | Gap >=3%, open above prior 20D high, gap remains unfilled, RVOL20 >=1.5x; catalyst is unavailable from OHLCV and is not asserted |

## Relative strength

- `kell_strength_on_down_day`: benchmark closes down while the stock closes non-negative on the aligned session.
- `kell_rs_divergence`: stock forms a higher low while the benchmark forms a lower low, or the benchmark is negative over the aligned 20-session window while the stock is non-negative.

SPY history is reconstructed from Unified's existing RS series, keeping the benchmark point-in-time aligned to the same Unified data.

## Cycle of Price Action

The v2 implementation treats these as a **sequence**, not unrelated breakout flags.

### Wedge Pop

Proxy for the first recapture through a tightening 10/20 EMA cluster after price has worked lower:

- current close crosses above the 10/20 EMA cluster;
- prior close was at/below the cluster;
- at least 3 of the previous 5 closes were at/below it;
- EMA10/EMA20 gap <=1.5%;
- prior 5D range <=70% of prior 15D range;
- recent highs are not materially above the preceding highs.

### EMA Crossback

Must follow a recent Wedge Pop:

- recent Wedge Pop within approximately 15 sessions;
- this is the **first** retest of the 10/20 EMA area after that pop;
- current low touches within ~1% of the EMA cluster;
- price holds the cluster on the close.

### Base n' Break

Longer consolidation supported by the short EMAs:

- at least 8 of the prior 10 closes hold at/above roughly 98% of the 20EMA;
- 10D range <=80% of 20D range;
- current close breaks the prior 10D high;
- close location >=55%.

### Tightening

Tightening requires:

- 5D median true range <=75% of the prior 15D median true range; and
- either 5D average volume <=85% of prior 15D average volume, or at least two inside bars in the last five sessions.

`kell_ttftl_warning` separately flags a Too-Tight-For-Too-Long style risk proxy when a long tight structure is accompanied by relative weakness.

## Kell Focus

`kell_focus` is a compact actionable research shortlist, **not a claim to reproduce a proprietary Kell watchlist**.

A name must first pass `kell_name_selection_ok`, then either:

1. pass the Buyable Gap proxy and have RS-leader or positive growth context; or
2. have a core Cycle entry setup (Wedge Pop, EMA Crossback, or Base n' Break), supportive context (RS divergence or weekly trend), at least one leadership signal (52W/new high, Bull Snort, 3M +50%, 6M Doubler, or RS leader), and no known-negative growth context.

All individual screens remain available independently.

## Score

`kell_score` is normalized to 0–100 over available criteria. v2 weights: Wedge Pop 12; Base n' Break 12; EMA Crossback 10; RS Divergence 10; Name Selection 8; Growth Context 8; 6M Doubler 8; Buyable Gap 8; Weekly Trend 8; Bull Snort 8; RS Leader 6; Strength on Down Day 6; EMA Readiness 6; 3M +50% 6; 52W/New High 5; Unusual Volume 5; Tightening 4; Breakout Proximity 4; broad Gapper 2. RVOL >=3x remains a separate discovery flag and is not double-counted.

## Validation — 2026-09-21 Unified session

Full deduplicated Unified pool: **2,683**, chart coverage **2,683/2,683**.

- Kell Focus: 6
- Growth Context: 264
- RS Rank >=90: 330
- 3M +50%: 139
- 6M Doubler: 131
- Bull Snort: 25
- Buyable Gap proxy: 10
- RS Divergence: 500
- Wedge Pop: 111
- EMA Crossback: 15
- Base n' Break: 51
- Tightening: 98

The ordinary Review Grid remained 80 candidates. CI passed 26 Python tests, the stored 2026-09-17 historical smoke, snapshot-link tests, GridView JavaScript syntax, and the live full-Unified build.

The prior v1 definitions were materially broader on the same live session: Tightening 2,042 and EMA Crossback 243. v2 reduced those to 98 and 15 by enforcing the Cycle structure rather than generic contraction or EMA recapture.

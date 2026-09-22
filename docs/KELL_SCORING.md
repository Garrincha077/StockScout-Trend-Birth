# Oliver Kell Overlay Scoring v3 — Screening Guide aligned

Branch scope: `feature/kell-mcp-lab`

This layer scans the **deduplicated union of all candidates already published by StockScout Unified** across Bottom, Next and Ryan. It does not create a new market-wide universe and does not alter Unified candidate generation, source ranks, or the ordinary Review Grid.

The model is `kell-overlay-v3-screening-guide`. v3 separates two things that were mixed together in v2:

1. **Published Kell screens** — use the explicit numerical criteria shown in Oliver Kell's Screening Guide / April 2024 Stock Selection webinar.
2. **Cycle of Price Action research proxies** — Wedge Pop, EMA Crossback, Base n' Break, tightening and readiness remain transparent deterministic approximations because Kell does not publish a complete machine-readable formula for those setups.

Primary public reference:
- https://theswingreport.com/wp-content/uploads/2024/04/Stock-Selection-Webinar-April-2024.pdf

## Source hierarchy

1. Existing Unified candidate membership.
2. Existing Unified daily OHLCV/chart history.
3. Unified embedded relative-strength series (`RS = stock / SPY * 100`) to reconstruct point-in-time SPY history.
4. Existing Unified context fields such as `rsRank`, growth fields and beta where available.
5. No external symbol may be added to the candidate pool by the Kell layer.

## Published screen formulas

| Screen | v3 operational definition |
| --- | --- |
| Bull Snort | Price > $20; Avg Vol 20D > 500k shares; stock up on the day; RVOL20 >=2.0x. Kell says 3x+ is preferred, so `kell_rvol_3x` remains a separate stricter flag. |
| 52 Week Highs | New 52-week high today; Price > $20; Avg Vol 20D > 500k; Beta >1. |
| Gappers | Price > $20; Avg Vol 20D > 500k; opening gap >3%. |
| Doublers | Price > $20; Avg Vol 20D > 500k; calendar YTD performance >100%. |
| Strength on Down Days | Price > $20; Avg Vol 20D > 500k; Beta >1; stock up on the day. Kell typically uses this screen when the market is down roughly 1–2% or more. |

Implementation notes:

- `kell_doubler_ytd` and compatibility alias `kell_doubler` are the canonical Doublers screen.
- `kell_doubler_6m` is retained only as a **legacy momentum diagnostic**; it is no longer treated as Kell's Doublers formula.
- `kell_down_market_context` is a separate context flag and becomes true when the reconstructed SPY session is down at least 1%. It is not baked into the published Strength screen formula.
- `kell_unusual_volume` (RVOL20 >=2x) and `kell_rvol_3x` remain standalone discovery flags across the Unified pool.
- `kell_buyable_gap_proxy` remains a stricter research overlay requiring an unfilled >3% gap, open above the prior 20D high and RVOL >=1.5x. It is not presented as Kell's published Gappers formula.

## Beta handling

The public 52 Week Highs and Strength on Down Days screens require Beta >1.

v3 uses:

1. an existing Unified beta field when one is present; otherwise
2. a point-in-time 126-session daily beta estimate versus the reconstructed SPY series, requiring at least 60 aligned return observations.

The beta fallback does not expand the universe and does not use Yahoo/MCP discovery.

## Name-selection and growth context

- `kell_name_selection_ok`: Price > $20 and Avg Vol 20D >500k, matching the common liquidity base in Kell's published screens.
- `kell_growth_context`: if both revenue YoY and EPS YoY exist, both must be >=25%; if only one numeric field exists, it must be >=25%; `fundamentalSupport` is used only when neither numeric growth field is available.
- `kell_rs_leader`: Unified RS rank >=90.
- `kell_weekly_trend_ok`: weekly close is at/above a rising 10-week EMA.

The growth, RS and weekly-trend fields are research context, not claims that they are additional filters in the five published screens above.

## Additional momentum context

| Signal | Definition |
| --- | --- |
| 3M +50% | 63-session return >=+50% |
| 6M +100% diagnostic | 126-session return >=+100%; stored as `kell_doubler_6m`, not the canonical Doubler |
| Near Breakout | Close within -3.0% to +1.5% of prior 20D high |
| RS Divergence | Stock higher-low while SPY lower-low, or stock non-negative over 20 sessions while SPY is negative |

## Cycle of Price Action proxies

The v3 implementation preserves the stricter v2 sequence logic.

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
- first retest of the 10/20 EMA area after that pop;
- current low touches within ~1% of the EMA cluster;
- price holds the cluster on the close.

### Base n' Break

- at least 8 of the prior 10 closes hold at/above roughly 98% of the 20EMA;
- 10D range <=80% of 20D range;
- current close breaks the prior 10D high;
- close location >=55%.

### Tightening

- 5D median true range <=75% of the prior 15D median true range; and
- either 5D average volume <=85% of prior 15D average volume, or at least two inside bars in the last five sessions.

`kell_ttftl_warning` separately flags a Too-Tight-For-Too-Long style risk proxy when a long tight structure is accompanied by relative weakness.

## Kell Focus

`kell_focus` is a compact research shortlist, **not a claim to reproduce a proprietary Kell watchlist**.

A name must first pass the common Kell liquidity base, then either:

1. pass the Buyable Gap proxy and have RS-leader or positive growth context; or
2. have a core Cycle entry setup (Wedge Pop, EMA Crossback, or Base n' Break), supportive context (RS divergence or weekly trend), at least one leadership signal (canonical 52W High, Bull Snort, 3M +50%, canonical YTD Doubler, or RS leader), and no known-negative growth context.

All published screens remain available independently as separate UI buckets.

## Score

`kell_score` is normalized to 0–100 over available criteria. v3 weights:

- Wedge Pop 12
- Base n' Break 12
- EMA Crossback 10
- RS Divergence 10
- Name Selection 8
- Growth Context 8
- YTD Doubler 8
- Buyable Gap proxy 8
- Weekly Trend 8
- Bull Snort 8
- RS Leader 6
- Strength on Down Day 6
- EMA Readiness 6
- 3M +50% 6
- canonical Gapper 6
- 52W High 5
- Unusual Volume 5
- Tightening 4
- Breakout Proximity 4

RVOL >=3x remains a separate discovery flag and is not double-counted.

## Output / UI contract

The compact preview exposes every candidate that hits at least one Kell screen/proxy and publishes `kellScoring.screenCounts`. The UI provides separate buckets for 52W Highs, Bull Snorts, RVOL >=3x, Doublers YTD, Gappers, Strength on Down Day, Cycle setups and the other research signals, with hit counts shown directly on the filter buttons.

The ordinary Review Grid candidate generation remains unchanged.

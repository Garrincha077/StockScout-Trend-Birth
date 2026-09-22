# Oliver Kell Overlay Scoring v4 — Screen / Stage / Setup separated

Branch scope: `feature/kell-mcp-lab`

This layer scans the **deduplicated union of all candidates already published by StockScout Unified** across Bottom, Next and Ryan. It does not create a new market-wide universe and does not alter Unified candidate generation, source ranks, or the ordinary Review Grid.

The model is `kell-overlay-v4-screen-stage-setup`. v4 makes the app contract explicit:

1. **SCREEN / discovery** — why the stock was surfaced (52W high, unusual volume/RVOL, Bull Snort, momentum/Doubler, Gapper, Strength on Down Day, RS leader proxy).
2. **STAGE / price cycle** — one primary current structural state, stored in `kell_stage.primary`, with confidence and a short evidence basis.
3. **SETUP / actionable pattern** — patterns or readiness conditions that may coexist with a stage (Buyable Gap proxy, Wedge Pop event, EMA Crossback event, Base n' Break event, Tightening, Near Breakout).
4. **CONTEXT** — supporting evidence such as liquidity, growth, RS divergence, weekly 10EMA and EMA readiness.

These dimensions are deliberately separate. A stock can have a strong screen while being in a poor or immature stage, and a stage is never inferred merely because a discovery screen fired.

Primary public reference:
- https://theswingreport.com/wp-content/uploads/2024/04/Stock-Selection-Webinar-April-2024.pdf

## Screen / Stage / Setup contract

`kellScreens`, `kellSetups` and `kellContext` are disjoint lists in the published payload.

`kell_stage` has:

- `primary`: one current structural state;
- `confidence`: deterministic confidence for that classification;
- `basis`: the evidence used for the classification.

Current primary stage values are:

- `wedge_pop`
- `ema_crossback`
- `base_n_break`
- `trend_ema_support`
- `downtrend_repair`
- `transition`
- `unavailable`

`kell_cycle_stage` remains as a compatibility alias for the primary stage.

The UI exposes separate filter groups for **Screens**, **Stage**, **Setups** and **Context**. A discovery hit does not automatically imply an actionable entry.

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

## Setup proxies and stage evidence

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

`kell_score` is normalized to 0–100 over available criteria. v4 keeps the same criterion weights, but also publishes separate `discovery`, `stage`, `setup` and `context` component scores:

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

## Validation — 2026-09-21 Unified session

Full deduplicated Unified pool: **2,683**, chart coverage **2,683/2,683**. The v4 compact Kell collection contains **2,063** names with at least one screen, setup or supporting context hit. This is the same broad matched-candidate coverage as the immediately preceding v3 baseline; candidate generation remains unchanged.

Discovery screens:

- 52 Week Highs: **3**
- Unusual Volume >=2x: **62**
- RVOL >=3x: **15**
- Bull Snort: **20**
- 3M +50%: **139**
- Doublers YTD: **39**
- Gappers: **58**
- Strength on Down Day: **246**
- RS Leader proxy: **330**

Actionable/setup layer:

- Buyable Gap proxy: **6**
- Wedge Pop setup: **111**
- EMA Crossback setup: **15**
- Base n' Break setup: **51**
- Tightening: **98**
- Near Breakout: **347**

Supporting context:

- Kell Focus: **6**
- Kell liquid/price base: **1,428**
- Growth Context: **264**
- RS Divergence: **500**
- Weekly 10EMA trend: **567**
- EMA10/20 Ready: **323**

Primary stock-stage classification among the 2,063 published Kell matches:

- Wedge Pop: **111**
- EMA Crossback: **15**
- Base n' Break: **49**
- Trend / EMA Support: **285**
- Downtrend / Repair: **1,091**
- Transition: **512**

The setup and stage counts are intentionally allowed to differ. For example, **51** stocks hit the Base n' Break setup while **49** have Base n' Break as their primary stage because one stock can satisfy multiple setup conditions while only one primary stage is published.

Real-output spot checks confirm the separation:
- **GRAL**: discovery screens include RVOL >=3x / Bull Snort / Gapper / RS Leader; primary stage = Base n' Break; setups include Buyable Gap and Base n' Break.
- **WBD**: discovery screens include RVOL >=3x / Bull Snort / Gapper; primary stage = Wedge Pop; multiple setup flags remain visible independently.
- **DELL**: strong discovery/context evidence but primary stage = Trend / EMA Support and no current actionable setup flag.

CI run **#111** passed unit tests, historical smoke, snapshot-link tests, GridView JavaScript syntax, the full live Unified rebuild, compact-data v4 validation, safe preview-data publication and artifact upload.

## Output / UI contract

The compact preview publishes separate `screenCounts`, `setupCounts`, `contextCounts` and `stageCounts`. The UI renders four distinct filter groups so discovery screens are not conflated with the stock's current Cycle-of-Price-Action stage or with an actionable setup.

The ordinary Review Grid candidate generation remains unchanged.

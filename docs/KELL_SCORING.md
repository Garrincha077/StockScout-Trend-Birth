# Oliver Kell Overlay Scoring v5 — Quality / Readiness / Context

Branch scope: `feature/kell-mcp-lab`

This layer scans the **deduplicated union of all candidates already published by StockScout Unified** across Bottom, Next and Ryan. It does not create a new market-wide universe and does not alter Unified candidate generation, source ranks, or the ordinary Review Grid.

The model is `kell-overlay-v5-quality-readiness-context`. v5 keeps the v4 Screen / Stage / Setup contract and replaces the naive additive ranking with a stage-aware composite:

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

- `reversal_extension`
- `wedge_pop`
- `ema_crossback`
- `base_n_break`
- `exhaustion_extension`
- `wedge_drop`
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

## Full-cycle stage proxies

The book's qualitative cycle is treated as structure, not as a claim that every stock follows every step. The lab now covers the missing outer phases with explicit numerical proxies:

- **Reversal Extension**: price must be materially extended below the daily 10EMA, reject a higher-timeframe-support proxy (50SMA, 200SMA or prior 60-session low), print a bullish upper-range reversal bar and show elevated volume. The current lab thresholds are >=5% downside extension, <=2% support proximity and >=1.5x 20D relative volume. These thresholds are lab proxies, not published Kell constants.
- **Exhaustion Extension**: only considered in an established short/intermediate uptrend (10EMA > 20EMA, rising 10EMA and positive prior trend). Price must make a fresh 20D high while the day's high is extended from the 10EMA by at least max(8%, 3x recent prior true-range median), with a blowoff clue from volume, gap or weak close location. This is deliberately stricter than simply being far above an EMA.
- **Wedge Drop**: requires a recent Exhaustion Extension proxy and a subsequent close that crosses below the 10/20 EMA cluster. It is a stage/risk-state event, not a discovery screen.

These values are intended to make Kell's qualitative descriptions reproducible and inspectable. They should be calibrated by historical precision tests rather than silently treated as canonical Kell rules.

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

## Score v5

The old v4 score is still calculated as `legacy_v4_score` for BEFORE/AFTER diagnostics, but it no longer determines ranking. The problem with v4 was correlated double counting: Bull Snort, RVOL, Gapper, RS and momentum could all award separate full points even when they described one underlying momentum / institutional-demand event.

The v5 final score is:

`Kell Focus = 35% Quality + 50% Readiness + 15% Context`

and is then constrained by the current Cycle-of-Price-Action stage. Missing contextual data uses a neutral prior rather than silently inflating the score, while `kell_evidence_coverage` reports how much supporting evidence was actually available.

### Quality (35%)

Quality asks whether the stock behaves like a Kell-type leader. Correlated clues are grouped into four families rather than stacked independently:

- **Institutional demand** — continuous RVOL strength plus bullish price response / close location.
- **Leadership** — continuous RS rank, 3-month momentum and proximity to the 52-week high.
- **Name quality** — continuous price and 20-day liquidity quality.
- **Higher-timeframe trend** — daily 10/20 EMA structure plus rising weekly 10EMA evidence.

The public discovery screens remain unchanged and independently filterable; this grouping affects ranking only.

### Readiness / Actionability (50%)

Readiness asks whether the stock is at a favorable current point in Kell's Cycle of Price Action. Stage baselines are intentionally unequal:

- EMA Crossback: 95
- Base n' Break: 92
- Wedge Pop: 88
- Trend / EMA Support: 72
- Reversal Extension: 65
- Transition: 50
- Downtrend / Repair: 28
- Exhaustion Extension: 30
- Wedge Drop: 10

Current setups then contribute a setup-quality score. Core entry setups dominate: EMA Crossback > Base n' Break > Wedge Pop > Buyable Gap proxy. Tightening and breakout proximity are smaller confirmation bonuses.

Where a natural Kell-style invalidation can be identified, v5 also computes a **structural-risk proxy**: distance from current price to the setup invalidation, normalized by recent true range. The numerical ATR-like cut-offs are lab proxies, not Kell-published rules.

### Stage caps

A high-quality leader cannot rank as a top current entry if it is late or structurally damaged. The final score and readiness are capped by stage:

| Stage | Maximum Focus / Readiness |
| --- | ---: |
| EMA Crossback | 100 |
| Base n' Break | 100 |
| Wedge Pop | 100 |
| Trend / EMA Support | 90 |
| Reversal Extension | 80 |
| Transition | 75 |
| Downtrend / Repair | 55 |
| Exhaustion Extension | 60 |
| Wedge Drop | 35 |
| Unavailable | 55 |

This is the key v5 behavior: a stock can remain an excellent **Quality** name while receiving a much lower **Readiness** score because it is extended, broken or simply not at a low-risk entry.

### Context (15%)

Context is deliberately smaller than price-cycle readiness:

- growth evidence from available revenue / EPS growth fields;
- RS divergence versus reconstructed SPY history.

### Evidence coverage

`kell_evidence_coverage` is a separate 0-100 measure based on availability of daily volume evidence, 3M/6M history, 52-week history, RS rank, weekly trend, growth evidence and benchmark-relative evidence. It is not a hidden bonus. A high Focus score with low coverage is therefore visibly less certain than a similar score with near-complete evidence.

### Published v5 fields

- `kell_score` — final stage-capped Kell Focus score.
- `kell_quality_score`
- `kell_readiness_score`
- `kell_actionability_score` — compatibility alias for readiness.
- `kell_context_score`
- `kell_evidence_coverage`
- `kell_structural_risk_score`
- `kell_stage_cap`
- `score_breakdown.legacy_v4_score` — diagnostic BEFORE score only.

## Live v5 validation — 2026-09-22 Unified session

Final CI run **#161 = SUCCESS** on commit `9febd946`, followed by the generated-data publication commit. The run passed unit tests, the historical 2026-09-17 smoke test, browser-model tests, JavaScript syntax, full Unified rebuild, compact v5 validation, live BEFORE/AFTER spot checks, publication and artifact upload.

Live coverage:

- Unified candidate union: **2,693**
- Kell matched candidates: **2,084**
- Chart coverage in compact Kell data: **2,084 / 2,084**
- Lazy chart shards: **44**
- Compact browser payload: **4,055,937 bytes**
- Session date: **2026-09-22**

The v5 rank now strongly separates name quality from current entry readiness. Live spot checks (`legacy v4 -> Focus v5`) were:

- **GRAL**: 33.3 -> **54.4**; Quality 81.7, Readiness 33.8, Context 59.6; stage = Exhaustion Extension, cap 60.
- **WBD**: 22.5 -> **52.9**; Quality 73.8, Readiness 47.8; stage = Transition.
- **DELL**: 34.3 -> **59.4**; Quality 60.8, Readiness 47.0, Context 97.3; stage = Transition.
- **VKTX**: 42.3 -> **73.6**; Quality 77.7, Readiness 87.7; stage = Wedge Pop.
- **AMD**: 50.8 -> **79.7**; Quality 74.3, Readiness 87.1; stage = Base n' Break.
- **TARS**: 18.6 -> **51.1**; Quality 45.1, Readiness 47.0; stage = Transition.

Top live v5 names began with **HALO 87.8**, **OKTA 83.1**, **SNX 81.8**, **BLLN 81.6**, **AAMI 80.7**, **SCCO 80.6**, **TTMI 80.5**, **MRVL 80.4**, **RSKD 79.9**, **AMD 79.7**. Importantly, the highest ranks are now dominated by Base n' Break / EMA Crossback readiness rather than simply by the largest number of correlated discovery hits.

The published discovery-screen definitions and candidate membership are unchanged by v5; only ranking/explainability changed.

## Historical v4 baseline — 2026-09-21 Unified session

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

Primary stock-stage classification among the 2,063 published Kell matches after the full-cycle refinement:

- Reversal Extension: **4**
- Wedge Pop: **111**
- EMA Crossback: **15**
- Base n' Break: **49**
- Exhaustion Extension: **6**
- Wedge Drop: **1**
- Trend / EMA Support: **285**
- Downtrend / Repair: **1,087**
- Transition: **505**

Before the full-cycle refinement, the generic buckets were Downtrend / Repair **1,091** and Transition **512**, with no Reversal Extension / Exhaustion Extension / Wedge Drop states. The new proxies therefore reclassified **11** names out of those generic buckets without changing any discovery-screen or setup counts.

The setup and stage counts are intentionally allowed to differ. For example, **51** stocks hit the Base n' Break setup while **49** have Base n' Break as their primary stage because one stock can satisfy multiple setup conditions while only one primary stage is published.

Real-output spot checks confirm the separation:
- **GRAL**: discovery screens include RVOL >=3x / Bull Snort / Gapper / RS Leader; primary stage = Base n' Break; setups include Buyable Gap and Base n' Break.
- **WBD**: discovery screens include RVOL >=3x / Bull Snort / Gapper; primary stage = Wedge Pop; multiple setup flags remain visible independently.
- **DELL**: strong discovery/context evidence but primary stage = Trend / EMA Support and no current actionable setup flag.
- **VKTX**: Reversal Extension stage with elevated volume / Bull Snort / Strength on Down Day evidence.
- **AMD**: Exhaustion Extension stage while still carrying separate Gapper / Bull Snort / RS-leader discovery hits and a Buyable Gap setup flag.
- **TARS**: Wedge Drop stage with no discovery-screen hit, demonstrating that the stage layer is not inferred from discovery membership.

The Exhaustion Extension proxy was tightened after the first live pass to require an established rising 10/20 EMA context plus a positive prior intermediate trend; live Exhaustion candidates fell from **12 to 6**, reducing rebound/dead-cat-style false positives.

CI run **#120** passed unit tests, historical smoke, snapshot-link tests, GridView JavaScript syntax, the full live Unified rebuild, compact-data v4 validation, safe preview-data publication and artifact upload.

## Output / UI contract

The compact preview publishes separate `screenCounts`, `setupCounts`, `contextCounts` and `stageCounts`. The UI renders four distinct filter groups so discovery screens are not conflated with the stock's current Cycle-of-Price-Action stage or with an actionable setup.

The ordinary Review Grid candidate generation remains unchanged.

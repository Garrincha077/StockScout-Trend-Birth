# StockScout Stage 1 Accumulation Model

Status: design specification / research hypothesis

Date: 2026-08-26

Related roadmap: `docs/ROADMAP.md`

## 1. Purpose

Long Stage 1 bases should not be treated as failed breakouts waiting for one decisive breakout event.

During a long structural base, the dominant behavior may be range trading for many months or years. A plausible institutional accumulation process can look like repeated demand near the lower or middle part of the range, supply/rebalancing near the upper part of the range, shakeouts of weak holders, and gradually improving absorption of overhead supply.

StockScout should therefore ask:

> Is the character of this long Stage 1 range changing in a way consistent with accumulation and supply absorption before the eventual Stage 1 -> Stage 2 transition?

The system must not claim that a specific institution is buying or selling. It should label only observable price/volume behavior as `institutional-looking`, `accumulation-like`, `absorption-like`, or similar evidence.

## 2. Key distinction: range accumulation is not breakout logic

Before trend birth, a healthy Stage 1 candidate may spend most of its time oscillating inside a range.

A useful conceptual sequence is:

`LONG RANGE -> REPEATED DEMAND -> SUPPLY ABSORPTION -> SHAKEOUTS / RECLAIMS -> RANGE TIGHTENING -> UPPER-RANGE ACCEPTANCE -> STAGE 1->2 TRANSITION`

The early StockScout objective is to detect the left and middle parts of this sequence.

LEGACY remains focused on later tradeable momentum setups and should not redefine this Stage 1 accumulation model.

## 3. What accumulation-like behavior may look like

### 3.1 Demand near the lower part of the range

Possible evidence:
- repeated tests of the lower quartile of the range that fail to produce durable downside progress;
- high or abnormal volume near range lows followed by closes well off the lows;
- quick reclaim after temporary breaks below support;
- progressively smaller downside excursion on repeated support tests;
- stronger forward returns after low-range volume events than after comparable ordinary days;
- lower-range tests followed by multi-day or multi-week stabilization rather than continued liquidation.

Possible fields:
- `rangePositionPct`;
- `lowerRangeDemandEvents`;
- `supportTestCount`;
- `supportTestSuccessRate`;
- `downsideProgressPerVolume`;
- `lowRangeRecoveryStrength`.

### 3.2 Upper-range selling does not automatically mean distribution

In a long Stage 1 range, price may repeatedly encounter supply near the upper boundary while larger buyers continue building positions elsewhere in the range.

StockScout should distinguish destructive distribution from constructive supply absorption.

Constructive signs may include:
- repeated upper-range rejection without a breakdown to new lows;
- pullbacks from the upper range becoming shallower over time;
- declining volume on pullbacks after upper-range tests;
- the range midpoint or rising long-term MA increasingly acting as support;
- less time spent in the lower half of the range after each resistance test;
- repeated resistance tests occurring at progressively shorter intervals;
- price impact from selling decreasing even when volume remains elevated.

Possible fields:
- `upperRangeSupplyEvents`;
- `pullbackDepthTrend`;
- `lowerHalfTimeShare`;
- `resistanceRetestIntervalTrend`;
- `sellingPriceImpactTrend`;
- `midRangeAcceptance`.

## 4. Weak-hand shakeouts / undercut-and-reclaim behavior

Long bases often contain false breaks or shakeouts before a durable trend begins.

Potentially constructive events:
- brief undercut of an established range low followed by a fast reclaim;
- high-volume selloff that fails to produce continued downside;
- close back inside the prior range after a support break;
- subsequent test holding above or near the reclaimed level;
- reduced selling pressure on the next pullback.

These should not automatically become bullish signals. They are evidence that must be evaluated in the context of the full base.

Possible fields:
- `undercutReclaimCount`;
- `shakeoutRecoveryDays`;
- `failedBreakdownRate`;
- `postShakeoutSupportQuality`;
- `downVolumeDecayAfterShakeout`.

Desired UI examples:
- `SHAKEOUT RECLAIM`
- `FAILED BREAKDOWN`
- `SUPPORT ABSORPTION`

## 5. Price/volume asymmetry inside the range

The core research idea is not simply `high volume = good`.

StockScout should measure whether volume produces asymmetric price outcomes.

Examples:
- large volume with limited downside progress can indicate supply being absorbed;
- moderate volume with strong upside progress can indicate reduced overhead supply;
- repeated up-volume events followed by quiet pullbacks can be constructive;
- repeated down-volume events with expanding downside range are destructive and should count against the accumulation thesis.

Candidate metrics:
- upside price change per unit of relative volume;
- downside price change per unit of relative volume;
- rolling up-volume / down-volume ratio;
- abnormal-volume event outcome after 5D / 20D;
- volume-weighted close location value;
- weekly accumulation/distribution event balance;
- trend in price impact per dollar volume.

## 6. Range geometry should evolve over time

A long Stage 1 range should be treated as a dynamic structure, not one fixed rectangle.

Track:
- base age;
- rolling range width;
- whether the effective floor is rising;
- whether the effective ceiling is flat, falling, or being repeatedly tested;
- midpoint slope;
- percentage of closes in upper versus lower half;
- higher-low sequence quality;
- volatility compression;
- time between support and resistance tests;
- proportion of total base volume transacted in the upper half versus lower half.

Potential constructive evolution:

`wide range -> stable floor -> rising internal lows -> more time in upper half -> smaller pullbacks -> tighter range -> upper-range acceptance`

This progression may be more important than a single breakout candle.

## 7. Stage 1 accumulation substates

The broader StockScout lifecycle can contain more detailed Stage 1 substates.

### RANGE / NEUTRAL
- long base exists;
- no persistent evidence of demand dominance;
- price still rotates symmetrically through the range.

### RANGE ACCUMULATION
- repeated constructive low/mid-range demand events;
- downside progress becomes harder;
- price/volume asymmetry improves;
- no durable breakout yet.

### SUPPLY ABSORPTION
- repeated upper-range tests;
- pullbacks become shallower;
- selling has less price impact;
- price spends more time in the upper half.

### TIGHTENING
- volatility and range width contract;
- internal lows rise or support firms;
- long-term MA structure flattens/turns;
- volume often dries up between demand events.

### PRE-TRANSITION / UPPER-RANGE ACCEPTANCE
- price can hold near resistance rather than immediately mean-revert;
- failed breakouts recover quickly;
- resistance retests become more frequent;
- RS and MA behavior begin to accelerate;
- first genuine Stage 1 -> 2 attempt becomes plausible.

These substates are descriptive evidence states, not automatic buy signals.

## 8. What should invalidate the accumulation thesis

StockScout must also detect when a long range is simply dead money or active distribution.

Negative evidence:
- repeated support breaks with increasing downside follow-through;
- lower lows after high-volume sell events;
- progressively deeper pullbacks;
- rising down-volume with weak recoveries;
- long-term MA structure rolling down again;
- RS deterioration versus both market and group;
- range ceiling falling faster than the floor rises;
- expanding volatility to the downside;
- repeated failed reclaims;
- worsening fundamentals or group deterioration when relevant.

Possible labels:
- `DISTRIBUTIVE RANGE`
- `SUPPORT DETERIORATING`
- `FAILED ACCUMULATION`
- `RANGE BREAKDOWN RISK`

## 9. Relationship to breakout detection

Breakout should be a later state transition, not the first moment StockScout becomes interested.

The eventual transition becomes more credible when several pre-breakout changes already exist:
- supply absorption near the upper range;
- shrinking pullback depth;
- rising internal lows;
- increasing upper-half occupancy;
- RS inflection/acceleration;
- MA slope turn;
- constructive volume asymmetry;
- group/fundamental improvement where applicable;
- low overhead resistance beyond the base.

The breakout then confirms a process StockScout has already been monitoring.

This is a core product distinction:

> StockScout should discover the stock during accumulation and maturation of Stage 1, not only after the breakout has made the trend obvious.

## 10. Research and validation requirements

All accumulation concepts above are hypotheses until tested.

Historical research should compare long Stage 1 bases that later became major winners with bases that failed.

For each base, reconstruct rolling weekly/daily snapshots and test:
- where abnormal volume occurred inside the range;
- how price responded to low-range versus high-range volume;
- whether support tests improved over time;
- whether pullbacks became shallower;
- whether failed breakdowns/reclaims preceded successful transitions;
- when RS and MA slopes changed;
- when upper-range occupancy increased;
- how long before breakout these effects became detectable;
- which combinations reduced false positives.

Avoid coding a fixed `accumulationScore` before this study. Start with transparent raw fields, event counts, trends, and lifecycle labels.

## 11. Initial UI concept

For a long Stage 1 candidate, the detail view could expose a compact evidence block such as:

`2.8Y BASE`  
`RANGE ACCUMULATION`  
`5 LOW-RANGE DEMAND EVENTS`  
`2 SHAKEOUT RECLAIMS`  
`PULLBACK DEPTH IMPROVING`  
`UPPER-HALF OCCUPANCY 68%`  
`SUPPLY ABSORPTION: DEVELOPING`  
`RS INFLECTING`  
`40W FLATTENING`  
`BREAKOUT: NOT REQUIRED YET`

This should visually communicate that the candidate is interesting because of a developing accumulation process, not because a breakout already happened.

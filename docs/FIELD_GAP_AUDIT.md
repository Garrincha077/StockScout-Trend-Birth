# StockScout Trend Birth — Field Gap Audit

Status: template / Step A deliverable

Date: 2026-08-26

Reference source: `Garrincha077/StockScreener-next`

## Purpose

Before importing implementation code, map the current StockScout fields/components to the new Trend Birth thesis.

Classify each component as:
- `KEEP`
- `EXTEND`
- `REPLACE`
- `DROP`

The classification should be based on whether the component helps detect early structural trend birth, not whether it already exists or is technically polished.

## Audit matrix

| Component / field | Current purpose | Trend Birth relevance | Historical context available? | Decision | Missing evidence / required change | Source files |
|---|---|---|---|---|---|---|
| Stage | TBD | High | TBD | TBD | Need maturity/transition/trend-age history | TBD |
| RS | TBD | High | TBD | TBD | Need 20D/60D/120D velocity + acceleration | TBD |
| MA Cluster | TBD | High | TBD | TBD | Need compression duration and slope-turn sequence | TBD |
| Emerging Leader | TBD | High | TBD | TBD | Compare semantics to lifecycle model | TBD |
| Opportunity v2 | TBD | Unknown | TBD | TBD | Determine redundancy / mature-momentum bias | TBD |
| Group Leadership | TBD | High | TBD | TBD | Need group-rank velocity / breadth emergence | TBD |
| Fundamentals | TBD | High for Investing | TBD | TBD | Need point-in-time inflection/trajectory | TBD |
| Chart mapping | TBD | Infrastructure | n/a | TBD | Likely reusable | TBD |
| Historical price ingestion | TBD | Infrastructure | TBD | TBD | Need 10Y+ depth if possible | TBD |

## Required audit questions

### Stage
- Is the present implementation point-in-time or only current-state?
- Can it distinguish early/mature/late Stage 1?
- Can it reconstruct Stage history?
- Can it identify the first Stage 2 transition versus later continuation?

### Relative strength
- What benchmark and window are currently used?
- Is historical RS rank stored or reproducible?
- Can velocity and acceleration be derived without look-ahead?
- Can RS versus group be added cleanly?

### MA structure
- Which MAs are available historically?
- Is slope history available?
- Can compression duration be reconstructed?
- Can falling -> flat -> rising transitions be expressed explicitly?

### Stage 1 range behavior
- Does any current module model dynamic range geometry?
- Are support/resistance tests stored?
- Are abnormal-volume events contextualized by range position?
- Can undercut/reclaim and price-impact metrics be built from existing OHLCV history?

### Resistance runway / overhead supply
- Is multi-year history deep enough?
- Are major prior highs/congestion zones available?
- Is volume-at-price feasible from current source data?

### Fundamentals
- Are historical values point-in-time or latest-only?
- Which fields can support acceleration/inflection without look-ahead?
- How reliable are estimates/revisions if available?

### Group leadership
- Is group mapping historically stable?
- Can historical group ranks be reconstructed?
- Can breadth and rank velocity be calculated?

### Opportunity / ranking
- Which current inputs reward mature momentum?
- Which inputs are genuinely early-cycle?
- Does one universal score obscure lifecycle differences?
- Which fields should remain raw evidence rather than ranking inputs?

## Deliverable standard

The completed audit must include:
1. exact source file/function references;
2. a `KEEP / EXTEND / REPLACE / DROP` decision for each relevant component;
3. historical-depth limitations;
4. point-in-time / look-ahead risks;
5. missing raw fields required by `docs/ROADMAP.md` and `docs/STAGE1_ACCUMULATION_MODEL.md`;
6. an implementation sequence that reuses infrastructure without inheriting obsolete scoring constraints.

No scoring redesign should begin until this audit is materially complete.

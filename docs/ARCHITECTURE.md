# StockScout Trend Birth — Initial Architecture

Status: greenfield design baseline

Date: 2026-08-26

## Mission boundary

This repository is free to redesign StockScout around early-cycle discovery.

The architectural contract is conceptual rather than implementation-preserving:

- **StockScout Trend Birth** = position/trend + investing discovery.
- **LEGACY** = separate frozen swing/momentum setup engine.

Do not blend the two into one opaque score.

## Reference source

`Garrincha077/StockScreener-next` is the preferred source of proven reusable components and data contracts.

Reuse is selective. Every imported component should be classified as:
- `KEEP` — useful largely as-is;
- `EXTEND` — good foundation but missing temporal/early-cycle context;
- `REPLACE` — concept useful, implementation no longer fits;
- `DROP` — not aligned with the new mission.

`Garrincha077/stock-screener2` remains stable fallback and is not a development target for this repo.

## Proposed layers

### 1. Market data / history layer

Provide reproducible daily and weekly price/volume history with enough depth to study multi-year bases and prior cycles.

Minimum desired capabilities:
- split-adjusted OHLCV;
- long history, preferably 10Y+ where available;
- weekly aggregation;
- benchmark history;
- sector/group mapping;
- fundamental history with observation timestamps;
- survivorship-aware historical universe where feasible.

### 2. Structural map layer

Build the long-term geometry of the ticker:
- major highs/lows;
- structural bases;
- prior-cycle reset;
- Stage history;
- long-term MA history;
- resistance and supply zones;
- resistance runway;
- trend age and breakout count.

Output should be raw evidence, not a universal score.

### 3. Stage 1 range behavior layer

Dedicated subsystem for long bases before breakout.

Responsibilities:
- dynamic range boundaries;
- lower/mid-range demand events;
- upper-range supply events;
- undercut-and-reclaim / failed breakdown behavior;
- price-volume asymmetry;
- pullback-depth trend;
- higher-low development;
- upper-half occupancy;
- supply-absorption evidence;
- range tightening and upper-range acceptance.

See `STAGE1_ACCUMULATION_MODEL.md`.

### 4. Relative-strength transition layer

Track RS as a time series rather than a single rank:
- absolute RS rank;
- 20D/60D/120D history;
- velocity;
- acceleration;
- price-vs-RS divergence;
- benchmark and group-relative strength;
- threshold crossing persistence.

### 5. MA transition layer

Model:

`compression -> flattening -> slope turn -> early expansion -> established expansion`

Inputs should include MA slopes and their history, not only current distances.

### 6. Fundamental inflection layer

Focus on change:
- EPS/revenue trajectory;
- margin and FCF inflection;
- revisions and surprises where reliable;
- loss-to-profit transitions;
- operating leverage;
- business-cycle/product-cycle improvement.

Every field should carry observation/provenance dates to reduce look-ahead risk in research.

### 7. Group emergence layer

Model group leadership dynamically:
- current rank;
- rank velocity;
- breadth;
- number of improving constituents;
- RS acceleration;
- whether the ticker leads or merely follows the group.

### 8. Attention / catalyst evidence layer

Optional supporting evidence:
- earnings gaps;
- abnormal price/volume events;
- guidance or estimate changes;
- contract/product/regulatory events where reliable.

Price/volume evidence remains primary.

### 9. Lifecycle classifier

Initial lifecycle:

`DORMANT -> ACCUMULATING -> AWAKENING -> LATE STAGE 1 -> STAGE 1->2 -> EARLY LEADER -> ESTABLISHED LEADER -> MATURE/LATE CYCLE`

The classifier must expose:
- state;
- confidence;
- supporting evidence;
- contradicting evidence;
- transition history.

A state label without reasons is insufficient.

### 10. Ranking layer

Do not build this first.

Preferred eventual design:
1. lifecycle state;
2. evidence strength within state;
3. Position and Investing lenses;
4. explicit penalties for maturity, failed accumulation, distribution, and overhead supply.

A universal mega-score is optional, not assumed.

### 11. Research / validation layer

Historical study is a first-class subsystem, not an afterthought.

Must support:
- point-in-time feature reconstruction;
- winner cohorts and failure/control cohorts;
- feature prevalence;
- lead-time analysis;
- 20D/60D/120D/250D outcomes;
- MFE/MAE;
- transition probability;
- ablation;
- false-positive and miss analysis.

### 12. Product layer

The UI should emphasize state change and evidence.

Potential screens:
- Accumulating
- Awakening
- Late Stage 1
- 1->2 Transition
- Early Leaders
- Long Base / Low Overhead Supply
- Fundamental Inflection
- New Attention / High Volume
- Failed Accumulation / Downgrade

Important daily events:
- first accumulation-like event;
- RS inflection;
- MA slope turn;
- first upper-range acceptance;
- lifecycle upgrade;
- lifecycle downgrade;
- first Stage 2 transition attempt.

## Initial data object direction

A per-ticker snapshot should eventually resemble:

```text
identity
marketContext
structuralBase
resistanceRunway
stageHistory
rangeBehavior
accumulationEvidence
relativeStrengthHistory
maTransition
fundamentalInflection
groupEmergence
attentionEvidence
lifecycle
riskEvidence
provenance
```

Each block should remain inspectable and independently testable.

## Import policy from StockScreener-next

Do not copy the entire old application blindly.

Prefer:
1. audit the existing component;
2. define the new required contract;
3. import only reusable code/data logic;
4. add an adapter if necessary;
5. write new tests around the Trend Birth behavior;
6. preserve source provenance in documentation.

Likely early reuse candidates:
- historical price ingestion;
- charting;
- basic RS calculations;
- basic Stage calculations;
- selected MA utilities;
- fundamentals ingestion;
- group mapping;
- publication/runtime infrastructure.

Likely redesign candidates:
- Opportunity v2 ranking;
- Emerging Leader semantics;
- static MA Cluster interpretation;
- static Stage label;
- any ranking that favors mature momentum without trend-age context.

## Branching and development

- `main` = controlled baseline.
- Create small topic branches for meaningful implementation work.
- Research notebooks/scripts may iterate faster, but promoted feature definitions must become reproducible code and documented evidence.
- No production cutover is implied by progress in this repo.

## Immediate architecture deliverable

Before implementing the new engine, create `docs/FIELD_GAP_AUDIT.md` mapping the current StockScreener-next fields/components to `KEEP / EXTEND / REPLACE / DROP`, with reasons and missing historical context.

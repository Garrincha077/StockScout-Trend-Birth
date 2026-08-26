# Research Workspace

This directory is for reproducible research supporting StockScout Trend Birth.

## Primary research question

> What did major future winners look like before they became obvious momentum leaders, and which observable features separate genuine trend birth from failed accumulation or dead money?

## Core study families

### 1. Historical major-winner study

Candidate outcome cohorts:
- +50% within 6-12 months;
- 2x within 12-24 months;
- 3x / 5x over longer windows;
- sustained high relative-strength leadership.

Observation windows should include multiple pre-event snapshots, such as 240D, 120D, 60D and 20D before transition.

### 2. Failed Stage 1 / false-start controls

Include long bases that:
- never transitioned to Stage 2;
- broke out and quickly failed;
- showed apparent accumulation but later distributed;
- remained dead money;
- experienced fundamental/group deterioration.

### 3. Stage 1 accumulation study

Test the hypotheses in `docs/STAGE1_ACCUMULATION_MODEL.md`:
- lower-range demand behavior;
- undercut-and-reclaim events;
- supply absorption;
- pullback-depth trend;
- upper-half occupancy;
- price/volume asymmetry;
- resistance-retest frequency;
- range tightening;
- RS and MA transition timing.

### 4. Lead-time study

Measure how early StockScout could have detected a later winner relative to:
- first major breakout;
- Stage 2 confirmation;
- later classic momentum/LEGACY setup.

### 5. Feature ablation

For every promoted ranking feature, ask:
- does it add information beyond Stage/RS alone?
- does it improve winner capture without exploding false positives?
- does it improve lead time?
- is it redundant with another field?

## Research rules

- Avoid survivor-only samples.
- Preserve point-in-time data where applicable.
- Record universe construction and delisting handling.
- Do not use future fundamentals in historical snapshots.
- Keep raw evidence and derived labels separately inspectable.
- Prefer reproducible scripts over manual chart anecdotes.
- Manual chart review is valuable for hypothesis generation, not sufficient for promotion by itself.

## Suggested project structure

```text
research/
  datasets/
  cohorts/
  notebooks/
  scripts/
  reports/
  fixtures/
```

Do not commit large proprietary/raw datasets without an explicit data-storage decision. Small reproducible fixtures are encouraged.

## Minimum outcome metrics

- 20D / 60D / 120D / 250D forward return;
- benchmark-relative return;
- MFE;
- MAE;
- maximum drawdown;
- Stage 2 transition rate;
- failed-transition rate;
- time to breakout;
- time to later LEGACY/momentum setup when available;
- major-winner capture rate;
- miss rate;
- precision by lifecycle state.

The objective is not to prove one trader's rules. The objective is to discover which measurable early-cycle characteristics are genuinely useful for StockScout.

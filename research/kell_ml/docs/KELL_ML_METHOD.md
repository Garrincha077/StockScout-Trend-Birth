# Kell ML Method v0.1

## Source hierarchy

1. Oliver Kell source reference used by the project.
2. Gold labels: human-reviewed frozen historical snapshots.
3. Silver labels: transparent StockScout proxies used to bootstrap scale.
4. ML outputs: statistical estimates, never promoted to "Kell rules".

## Separate learning problems

### Structure

Question: What is the current chart state using only information available on that date?

Initial Gold vocabulary:
- REVERSAL_EXTENSION
- WEDGE_POP
- EMA_CROSSBACK
- BASE_N_BREAK
- EXHAUSTION_EXTENSION
- WEDGE_DROP
- REPAIR_OR_OTHER

### Opportunity

Question: Given a point-in-time state and evidence, what later outcome distribution did comparable states have?

Forward return, MFE and MAE may define targets but cannot enter model features.

## Historical sampling

Do not train only on current StockScout scans. Historical samples should include:
- future major winners before they became obvious;
- first EMA recaptures and first retests;
- large-base breakouts;
- abnormal-volume events;
- RS leaders during QQQ weakness;
- failed breakouts;
- late/extended leaders;
- repeated second/third/fourth EMA touches;
- tight but relatively weak bases;
- random/control observations.

For major winners, collect multiple frozen snapshots before and around trend birth, not only the eventual breakout.

## Evaluation discipline

Use chronology, not random row splits. Preserve later periods as untouched holdouts when data coverage allows.

Structure metrics:
- macro F1;
- balanced accuracy;
- per-class precision/recall;
- confusion matrix;
- targeted reports for Wedge Pop vs ordinary recapture and first Crossback vs later retests.

Opportunity/ranking metrics:
- precision/recall at top-k;
- forward return distribution;
- MFE/MAE;
- failed-transition rate;
- winner capture and miss rate;
- lead time versus later StockScout/LEGACY detection.

## Promotion

No ML model changes production ranking until feature definitions are reproducible, leakage tests pass, Gold-label performance is measured, walk-forward results are documented, and BEFORE/AFTER candidate review shows useful improvement.

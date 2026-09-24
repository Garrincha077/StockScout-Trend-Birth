# Kell Gold Set

## Purpose

The Gold Set is a small, manually reviewed, **multi-session** calibration set for the Kell
overlay. It is **not** generated from the detector under test and it never changes the
Unified universe, screens, stages, setups, scores or rankings.

Labels live in `lab/data/kell-gold-set.json`.

## Labels

- `VALID` — the model published the signal and manual point-in-time review confirms a
  clean enough positive example.
- `BORDERLINE` — the model published the signal; core Kell structure is plausible, but
  execution/context is imperfect.
- `FALSE_POSITIVE` — the model published the signal, but manual point-in-time review
  concludes the concept is not actually present in the required structural/cycle context.
- `FALSE_NEGATIVE` — manual point-in-time review concludes the concept is present, but
  the model did not publish the signal.

A `FALSE_POSITIVE` must have `predictionAtReview=true`; a `FALSE_NEGATIVE` must have
`predictionAtReview=false`. Reviewed positives that the model missed must be labeled
`FALSE_NEGATIVE`, not `VALID` or `BORDERLINE`.

Each row is keyed by session date, ticker, layer and signal. The
`predictionAtReview` field is the BEFORE state. The evaluator compares it with the
archived/current prediction for that same session to produce AFTER metrics.

## Multi-session evaluation

`scripts/kell_gold_set.py` reads the Gold Set plus the current compact Kell payload,
point-in-time score archives, and optionally immutable raw EOD snapshots.

Older score archives may contain only stage data. When a requested setup/context field is
not archived, `--snapshots-dir` allows the evaluator to re-run the **current** Kell
scoring code over that session's stored candidate OHLCV. This does not alter the original
Unified candidate universe or historical bars. The report marks these rows with
`evaluationSource=raw_snapshot_rescore` so archived predictions and current-code
rescoring remain distinguishable.

The report includes, by signal bucket and by EOD session:

- reviewed/evaluated labels;
- BEFORE and AFTER predicted counts inside the reviewed set;
- labels lost or added versus baseline;
- accepted precision (`VALID + BORDERLINE + recovered FALSE_NEGATIVE`);
- strict clean precision (`VALID + recovered FALSE_NEGATIVE`);
- positive recall over all reviewed positives, including false negatives;
- weighted quality (`VALID/FALSE_NEGATIVE=1.0`, `BORDERLINE=0.5`,
  `FALSE_POSITIVE=0`);
- observed, fixed and unresolved false positives;
- observed, fixed and unresolved false negatives;
- hard regressions where a previously predicted `VALID` label disappears;
- labeled-session count and the number of sessions containing FP/FN evidence.

## Deliberate FP/FN sampling protocol

For Wedge Pop and Buyable Gap calibration, do not review only published signals.

For each independent EOD session:

1. inspect real StockScout/Unified candidates that **did** trigger the setup and deliberately
   look for structural contradictions (FP search);
2. inspect near misses around the proxy boundaries and deliberately look for Kell-consistent
   structures that the detector missed (FN search);
3. separate **setup structure** from name-selection/context quality;
4. record the exact point-in-time reason codes and keep ambiguous cases `BORDERLINE`
   rather than forcing an FP/FN;
5. require evidence across multiple independent sessions before changing a numerical proxy.

For Wedge Pop, review the sequence: prior decline/repair, tightening/coiling, tight 10/20
EMA cluster and meaningful recapture. Merely being above the EMAs is not sufficient, and a
repeated later recapture should not automatically be treated as the first Wedge Pop.

For Buyable Gap, review whether the gap clears meaningful resistance, remains open, has
volume/participation and occurs in constructive cycle context. A mechanically valid gap in
an already exhausted/extended stock can be a false positive for a *buyable* gap.

## Safety

The workflow uses `--strict` only to reject malformed labels and loss of reviewed
`VALID` positives. Removing a `BORDERLINE` signal, fixing a `FALSE_POSITIVE`, or
recovering a `FALSE_NEGATIVE` does not itself fail CI.

A proxy threshold must not be changed merely to improve this small set. Review real charts,
add counterexamples from independent sessions, compare BEFORE/AFTER, and keep Kell's
qualitative rules separate from StockScout numeric proxies.

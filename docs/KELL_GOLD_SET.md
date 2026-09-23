# Kell Gold Set

## Purpose

The Gold Set is a small, manually reviewed calibration set for the Kell overlay. It is
**not** generated from the detector under test and it never changes the Unified universe,
screens, stages, setups, scores or rankings.

Labels live in `lab/data/kell-gold-set.json`.

## Labels

- `VALID` — clean enough to preserve as a positive example.
- `BORDERLINE` — core Kell structure is plausible, but execution/context is imperfect.
- `FALSE_POSITIVE` — the model published the signal, but manual chart review concludes
  that the concept is not actually present.

Each row is point-in-time and keyed by session date, ticker, layer and signal. The
`predictionAtReview` field is the BEFORE state. The evaluator compares it with the
archived/current prediction for that same session to produce AFTER metrics.

## Evaluation

`scripts/kell_gold_set.py` reads the Gold Set plus the current compact Kell payload and/or
point-in-time score archives. It reports, by signal bucket:

- reviewed/evaluated labels;
- BEFORE and AFTER predicted counts inside the reviewed set;
- labels lost or added versus baseline;
- accepted precision (`VALID + BORDERLINE`);
- strict clean precision (`VALID` only);
- positive recall over reviewed positives;
- weighted quality (`VALID=1.0`, `BORDERLINE=0.5`, `FALSE_POSITIVE=0`);
- fixed and unresolved false positives;
- hard regressions where a previously predicted `VALID` label disappears.

Legacy archives may contain only stage data. In that case stage labels remain evaluable
while screen/setup/context labels are reported as unavailable rather than incorrectly
counted as negatives.

## Safety

The workflow uses `--strict` only to reject malformed labels and loss of reviewed
`VALID` positives. Removing a `BORDERLINE` signal or fixing a `FALSE_POSITIVE` does
not fail CI.

A proxy threshold must not be changed merely to improve this small set. Review real
charts, add counterexamples, and keep Kell's qualitative rules separate from StockScout
numeric proxies.

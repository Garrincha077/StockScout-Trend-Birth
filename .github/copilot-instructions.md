# StockScout Trend Birth — Copilot Review Instructions

Apply these rules to every pull-request code review in this repository.

## Review goal

Find real defects and methodology leaks with high signal-to-noise. Do not spend review budget on cosmetic style nits unless they create correctness, maintainability, or operational risk.

Classify every actionable finding as:
- **P0** — catastrophic: corrupts production data, leaks secrets, can execute unintended trades/actions, or makes the system broadly unusable.
- **P1** — serious: changes core candidate generation/ranking/scoring semantics unintentionally, breaks a major workflow, creates data-identity/look-ahead errors, or materially misleads stock selection.
- **P2** — meaningful: localized correctness/regression issue that should be fixed before merge.
- Lower-priority suggestions may be noted separately but must not be presented as blockers.

If there are no P0/P1/P2 findings, say so explicitly.

## Stock-selection semantics

Treat any change to candidate membership, ranking, scoring, stage assignment, filters, quick views, lifecycle states, alert eligibility, or ordering as methodology-sensitive.

For methodology-sensitive changes:
1. Identify the exact BEFORE and AFTER semantics.
2. Check whether a supposedly descriptive/evidence field has become a hidden gate, weight, rank, tie-breaker, or default selection priority.
3. Prefer reuse of an already-computed Unified signal over silently recomputing a second version in Trend Birth.
4. Flag score-only promotion when detector membership is supposed to require an explicit triggered setup.
5. Require transparent provenance for fields used in selection.
6. Check that watchlist/tracked names and Unified candidates use equivalent enrichment semantics where intended.
7. Do not accept a behavior/ranking change merely because CI is green; require a test that actually protects the intended invariant.

## Data and research integrity

Review for:
- stale or mixed snapshot/session/run identity;
- current data accidentally substituted for historical point-in-time data;
- look-ahead bias;
- fallback paths that silently change universe membership;
- survivor-only evaluation;
- missing/unavailable data treated as negative evidence;
- compact/sharded datasets dropping fields needed by the UI;
- duplicate calculations whose thresholds can drift apart.

## Architecture boundaries

Unless the PR explicitly states otherwise:
- do not modify the stable Unified EOD / production Telegram / broker behavior from Trend Birth lab work;
- keep experiments isolated from production;
- preserve the distinction between Unified detector outputs, Trend Birth lifecycle evidence, and Kell scoring;
- filters may narrow what is displayed, but should not silently redefine the source universe;
- explanatory evidence must not silently become ranking/scoring input.

## Verification

For meaningful behavior changes, look for:
- focused regression tests;
- relevant end-to-end CI;
- BEFORE/AFTER checks on real StockScout candidates where practical;
- failure-mode coverage, not only happy-path examples.

When a test only checks source-code shape with regex/string matching, say whether a behavioral test would materially improve protection.

## Review output

Lead with findings, highest severity first. For each finding include:
- severity;
- file/area;
- concrete failure mode;
- why it matters;
- smallest safe fix.

Then give:
- **P0/P1/P2 summary**
- **Regression status**
- **Methodology status**
- **Merge-gate status**

Never approve or recommend merging a PR that still has an unresolved P0/P1/P2 finding.

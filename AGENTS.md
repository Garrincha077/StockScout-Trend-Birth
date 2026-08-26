# StockScout Trend Birth — Agent Rules

Repository: `Garrincha077/StockScout-Trend-Birth`

Reference implementation: `Garrincha077/StockScreener-next`
Stable fallback: `Garrincha077/stock-screener2`

## Product contract

1. StockScout Trend Birth is an early-cycle **position/trend + investing discovery engine**.
2. The existing frozen Ryan/Minervini-style LEGACY engine is a separate **swing trading / momentum setup engine**.
3. Do not blend LEGACY into StockScout discovery as a hidden mandatory gate or opaque score.
4. The new engine should focus on trend birth: long structural bases, Stage 1 accumulation, supply absorption, RS inflection, MA slope turn, Stage 1 -> 2 transition, early leadership, resistance runway, fundamental inflection and emerging group leadership.
5. In long Stage 1, do not require breakout before interest. Range accumulation and supply absorption are first-class research targets.

## Greenfield freedom

This repository is not required to preserve current StockScout scoring or architecture.

It may redesign:
- scoring;
- ranking;
- lifecycle states;
- data schema;
- scan cadence;
- UI/workflow;
- historical context;
- research infrastructure.

However, reuse working code from `StockScreener-next` when it is genuinely useful rather than rebuilding infrastructure for its own sake.

For each imported component classify it as:
- `KEEP`
- `EXTEND`
- `REPLACE`
- `DROP`

## Research discipline

1. Practitioner ideas are hypotheses, not facts.
2. Distinguish observable price/volume behavior from inferred institutional intent.
3. Prefer labels such as `accumulation-like`, `supply-absorption-like`, or `institutional-looking` rather than claiming specific institutions are buying or selling.
4. Avoid survivor-only winner studies. Include failures and controls.
5. Avoid look-ahead bias. Fundamental and universe data must be point-in-time where research conclusions depend on them.
6. Prefer transparent raw fields, event counts, trends and lifecycle reasons before composite scores.
7. Do not optimize only for 5D/20D returns; the mission includes multi-month and multi-year trends.
8. Record false positives, false negatives and major missed winners, not only successful examples.

## Implementation discipline

1. `main` is the controlled baseline.
2. Use small topic branches for meaningful implementation changes.
3. Keep research prototypes isolated until their definitions are reproducible.
4. Add tests for promoted feature definitions and lifecycle logic.
5. Any historical-study result used to change ranking should include reproducible methodology and ablation/controls where practical.
6. Do not copy the entire `StockScreener-next` codebase blindly. Audit first, import selectively.
7. Do not modify `Garrincha077/stock-screener2` from this project.
8. Do not modify `Garrincha077/StockScreener-next` unless the user explicitly asks for a cross-repo change.
9. Never commit secrets or credentials.

## Durable project memory

After every meaningful code, workflow, data-contract, research-methodology or product-architecture change, update `docs/PROJECT_LOG.md`.

Record:
- date;
- branch and commit SHA(s);
- what changed and why;
- affected files/components;
- whether behavior/ranking/scoring changed;
- tests/audits/research validation performed and result;
- regression risks / methodological caveats;
- next logical step.

If chat history and GitHub disagree, treat this repository plus `docs/PROJECT_LOG.md` as durable truth.

## Required reading before substantial work

- `README.md`
- `docs/ROADMAP.md`
- `docs/STAGE1_ACCUMULATION_MODEL.md`
- `docs/ARCHITECTURE.md`
- `docs/PROJECT_LOG.md`

For architecture/reuse work also read the relevant source files and project docs in `Garrincha077/StockScreener-next` before deciding what to import.

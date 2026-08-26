# StockScout Trend Birth

Greenfield research and development project for early detection of new stock leadership cycles.

## Product thesis

StockScout Trend Birth is not a swing-entry screener. Its mission is to identify stocks during the birth of a potentially important multi-month or multi-year trend, before they become obvious mature momentum leaders.

The core question is:

> Is a new important trend being born here, early enough that it may still have months or years of runway?

The project focuses on long structural bases, Stage 1 accumulation, supply absorption, relative-strength inflection, moving-average compression and slope turn, Stage 1 -> Stage 2 transition, low overhead resistance, emerging group leadership, and fundamental inflection.

## Relationship to LEGACY

The existing frozen Ryan/Minervini-style LEGACY engine serves a different job:

- **LEGACY:** swing trading / momentum setup engine; days to weeks, occasionally months.
- **StockScout Trend Birth:** position/trend + investing discovery engine; weeks to months and potentially years.

LEGACY may later find tactical entries in a stock that StockScout discovered much earlier. That is expected and desirable.

## Conceptual lifecycle

`DORMANT -> ACCUMULATING -> AWAKENING -> LATE STAGE 1 -> STAGE 1->2 -> EARLY LEADER -> ESTABLISHED LEADER -> MATURE / LATE CYCLE`

The primary discovery target is the middle of that lifecycle, especially:

- ACCUMULATING
- AWAKENING
- LATE STAGE 1
- STAGE 1 -> 2
- EARLY LEADER

## Design principles

- Treat practitioner ideas as hypotheses to test, not unquestioned rules.
- Prefer transparent evidence fields and lifecycle states before opaque composite scores.
- Study winners and failures; avoid survivor-only research.
- Model Stage 1 as a dynamic range process, not merely a breakout waiting room.
- Do not claim institutional activity directly; describe observable accumulation-like / absorption-like price-volume evidence.
- Optimize for early discovery and long runway, not only 5D/20D returns.
- The current `Garrincha077/StockScreener-next` repository is a reference/source of proven infrastructure, not an architectural constraint.

## Documents

- [`docs/ROADMAP.md`](docs/ROADMAP.md) — full product and implementation roadmap.
- [`docs/STAGE1_ACCUMULATION_MODEL.md`](docs/STAGE1_ACCUMULATION_MODEL.md) — long Stage 1 range accumulation and supply-absorption research model.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — initial greenfield architecture and reuse boundaries.
- [`docs/PROJECT_LOG.md`](docs/PROJECT_LOG.md) — durable project history and handoff.
- [`research/README.md`](research/README.md) — historical winner/failure research workspace.

## Reference repositories

- `Garrincha077/StockScreener-next` — current-generation StockScout app and reusable reference implementation.
- `Garrincha077/stock-screener2` — stable fallback; do not modify from this project.

This repository is intentionally free to redesign scoring, ranking, lifecycle states, data schema, historical context, scan cadence, and UI if research evidence supports it.

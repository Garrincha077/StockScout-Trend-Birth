# Unified Review Grid Lab

This is an isolated, read-only companion to `Garrincha077/StockScout-Unified`.

## Safety boundary

- Never writes to StockScout Unified.
- No Telegram token, Supabase key, broker credential, or production secret is used.
- Reads only public, activated Unified Pages assets.
- The existing review lab baseline lives on `feature/unified-review-grid-lab`; Oliver Kell scoring work is isolated on `feature/kell-mcp-lab` until explicitly promoted.
- The lab may fail without affecting Unified scans, Pages, ranking, notifications, or owner state.

## Daily candidate set

The snapshot builder mirrors the active Unified modes:

- Bottom Fishing
- Next
- Ryan Original
- Kell daily leaders: up to 5 names from the full public Bottom pool that **must** pass a liquid positive-day `RVOL >= 3.0x` gate (`ADV50 >= $20M`, price >= $5); Unified Oliver Kell saved-screen confluence (Reclaim/Launch, 52W Highs, Bull Snort, Doublers) is preserved and used to rank the qualifying power moves
- Kell Gap-Up: canonical Oliver Kell Gappers screen (`price > $20`, `Avg Vol 20d > 500k`, `gap > 3%`), then the lab ranks the best daily matches by gap hold, close quality, RVOL and 50D/30W context. The canonical eligibility rule and the lab's quality ranking remain separately visible.

A ticker can have multiple source badges, for example `Bottom + Kell`. Kell match reasons are preserved in the ticker detail.

## Review UI

`index.html` renders one responsive GridView of all selected names. Tapping/clicking a chart opens that ticker's detail view with EMA10/20 proximity, 50D/30W slope, RSI14, base-width proxy, current HH/HL swing structure, close location and a deterministic trade-state review. A Work-written analysis object can override/extend the review with QoQ fundamentals and ticker-specific commentary.

The browser never needs cross-origin access to Unified chart shards. `scripts/build_review_snapshot.py` resolves chart history server-side. The ordinary Review Grid keeps its chart rows in the review snapshot; the full Kell candidate view publishes deterministic lazy-load OHLCV shards under `data/kell-charts/`, so charts are available for the full Kell result set without forcing the browser to download all chart history up front.

## AI analysis handoff

A Work task can write an analysis JSON object using the format shown in `data/analysis.example.json`, then run the snapshot builder with `--analysis`. This keeps research/AI analysis separate from deterministic Unified source data.

## Local build

```bash
python scripts/build_review_snapshot.py \
  --analysis lab/data/analysis.example.json \
  --output lab/data/latest.json
python -m http.server 8000 -d lab
```

Then open `http://localhost:8000/`.


## Candidate-only Kell v5 overlay

`scripts/kell_scoring.py` scores only candidates already present in the deduplicated Unified Bottom / Next / Ryan universe. It never expands candidate membership and does not alter the production Unified pipeline.

The browser keeps **Universe** as the parent filter and then applies one secondary Screen / Stage / Setup / Context filter inside that universe.

The v5 ranking deliberately separates:

- **Quality** — institutional demand, leadership, liquidity/name quality and higher-timeframe trend;
- **Readiness / Actionability** — current Kell price-cycle stage, active setup quality and structural-risk proxy;
- **Context** — growth and benchmark-relative evidence;
- **Evidence coverage** — how much supporting data was actually available.

`Kell Focus` is the final 0–100 ranking:

`35% Quality + 50% Readiness + 15% Context`

with stage caps so late-cycle `Exhaustion Extension`, `Wedge Drop` and repair states cannot rank like clean low-risk entries merely because they also have strong RVOL, gap or momentum signals.

The old additive v4 score is retained only as `legacy_v4_score` for reproducible BEFORE/AFTER diagnostics. The UI shows Focus, Quality, Readiness, Context, evidence coverage, stage and current setups separately.

### Unified-wide Kell filters

Discovery filters remain independent of ranking and continue to scan the deduplicated Unified candidate union: 52W/New High, unusual volume, RVOL >=3x, Bull Snort, 3M momentum, Doublers YTD, Gappers, Strength on Down Day and RS Leader.

Stage remains a separate single structural classification, while setup filters include Buyable Gap proxy, Wedge Pop, EMA Crossback, Base n' Break, Tightening and Near Breakout. Supporting-context filters remain separate as well.

The boolean `kell_focus` research shortlist is labelled **Kell Shortlist** in the UI so it is not confused with the numerical **Kell Focus score**.

See `docs/KELL_SCORING.md` for the exact v5 formulas, explicit proxy thresholds and source-grounding notes.

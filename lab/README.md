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


## Candidate-only Kell score overlay

\`scripts/kell_scoring.py\` adds a transparent 0–100 Oliver Kell-style score to every candidate already selected by the review pipeline. It does not add candidates or alter the existing default order. The UI exposes a score badge, \`Kell >=60\` filter, score sort, and full per-criterion breakdown.

See \`docs/KELL_SCORING.md\` for exact v1 thresholds, weights and methodology.

### Unified-wide Kell filters

Kell filters scan the deduplicated union of all published Bottom, Next and Ryan candidates, not only the normal top Review Grid rows. Separate filters are available for 52W/New High, unusual volume, RVOL >=3x, Bull Snort, Doublers, Gappers, Strength on Down Day, EMA readiness, Wedge Pop, EMA Crossback, Base n' Break, Tightening and Near Breakout. The normal All/Bottom/Next/Ryan review board is unchanged.


### Kell v2 PDF-grounded workflow

The Kell lab now follows a v2 workflow grounded in *Victory in Stock Trading*. All published Unified candidates are still scanned, but 3M +50% momentum and true 6M +100% Doublers are separate lists. Wedge Pop, EMA Crossback and Base n' Break are sequence-aware, not generic EMA/breakout flags. Additional filters expose RS divergence, weekly 10EMA context, growth context, RS rank >=90 and a stricter Buyable Gap proxy.

`Kell Focus` is the compact research shortlist that combines liquidity/price, leadership or growth evidence, and a core Kell entry setup. It does not replace the individual full-Unified filters. The ordinary All/Bottom/Next/Ryan Review Grid remains unchanged.

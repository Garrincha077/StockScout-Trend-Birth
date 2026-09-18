# Unified Review Grid Lab

This is an isolated, read-only companion to `Garrincha077/StockScout-Unified`.

## Safety boundary

- Never writes to StockScout Unified.
- No Telegram token, Supabase key, broker credential, or production secret is used.
- Reads only public, activated Unified Pages assets.
- Development lives on `feature/unified-review-grid-lab` until explicitly promoted.
- The lab may fail without affecting Unified scans, Pages, ranking, notifications, or owner state.

## Daily candidate set

The snapshot builder mirrors the active Unified modes:

- Bottom Fishing
- Next
- Ryan Original
- Kell daily leaders: top 5 names from the full public Bottom pool matching Unified's existing Oliver Kell saved-screen rules (Reclaim/Launch, 52W Highs, Bull Snort, Doublers) plus a liquid daily `RVOL >= 3.0x` overlay (`ADV50 >= $20M`, price >= $5, positive day)

A ticker can have multiple source badges, for example `Bottom + Kell`. Kell match reasons are preserved in the ticker detail.

## Review UI

`index.html` renders one responsive GridView of all selected names. Tapping/clicking a chart opens that ticker's detail view.

The browser never needs cross-origin access to Unified chart shards. `scripts/build_review_snapshot.py` copies only selected candidates and their required public chart rows into `data/latest.json` during the build.

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

# StockScout Trend Birth — Persistent Project Log

This file is the durable handoff for `Garrincha077/StockScout-Trend-Birth`.

Update it after every meaningful code, workflow, data-contract, research-methodology or product-architecture change.

## 2026-08-26 — Greenfield repository bootstrap

- Repository: `Garrincha077/StockScout-Trend-Birth`.
- Branch: `main`.
- Bootstrap commits:
  - `85683572d08fbcb3b5ce0e5e96e1088ff189a756` — README / product thesis;
  - `f7dc973607332c9a70e1019c660a0f937cec404b` — full Trend Birth roadmap;
  - `2aa41ad69f83b883ad1ba1057aa1ab1181737877` — Stage 1 accumulation/range model;
  - `0af1a0844c5d4fef4f58c5757c2bd4c00e59c26a` — initial greenfield architecture;
  - `2fc2f3de49cf47c31a668b440aaf8006a2a1b3f0` — agent/research/implementation rules;
  - `ffe0bd7e3ec52e72285e1988b377cd17fb412ca6` — historical research workspace;
  - `abd1bd5e2c4b331c965a6687a5505deda37ba16f` — Step A field-gap audit template.
- Product decision: **LEGACY remains a separate swing trading / momentum setup engine. StockScout Trend Birth is a position/trend + investing discovery engine focused on early structural trend birth.**
- Core lifecycle baseline: `DORMANT -> ACCUMULATING -> AWAKENING -> LATE STAGE 1 -> STAGE 1->2 -> EARLY LEADER -> ESTABLISHED LEADER -> MATURE/LATE CYCLE`.
- Stage 1 decision: long Stage 1 is modeled as a dynamic range process. StockScout should look for accumulation-like demand, supply absorption, undercut/reclaim behavior, shrinking pullbacks, rising internal lows, upper-half occupancy, tightening and upper-range acceptance **before** requiring breakout.
- Research language guardrail: observable price/volume behavior may be described as accumulation-like, absorption-like or institutional-looking; the system must not claim that specific institutions are buying/selling without direct evidence.
- Architecture decision: `Garrincha077/StockScreener-next` is a reference/source of proven infrastructure, not an architectural constraint. Components must be audited as `KEEP / EXTEND / REPLACE / DROP` before selective reuse. `Garrincha077/stock-screener2` is not to be modified from this project.
- Ranking/scoring decision: no commitment to Opportunity v2 or any current StockScout score. Do not build a new opaque mega-score before raw evidence and historical studies are understood. Lifecycle/state-first ranking is the preferred hypothesis, pending evidence.
- Affected files: `README.md`, `AGENTS.md`, `docs/ROADMAP.md`, `docs/STAGE1_ACCUMULATION_MODEL.md`, `docs/ARCHITECTURE.md`, `docs/FIELD_GAP_AUDIT.md`, `research/README.md`, and this log.
- Behavior/model impact: documentation/research architecture only. No executable scanner, ranking, scoring, workflow, publication path or production behavior exists in this repo yet.
- Tests/audits/CI: none required for documentation-only bootstrap; no CI-green claim is made.
- Main regression/methodological risks: survivor bias, look-ahead bias in fundamentals/universe membership, mistaking one-off volume spikes for accumulation, overfitting Stage 1 range rules, and importing mature-momentum biases from the current-generation StockScout ranking.

**Next logical step**
- Execute **Step A — Architecture and historical audit** against `Garrincha077/StockScreener-next`.
- Fill `docs/FIELD_GAP_AUDIT.md` with exact source files/functions and classify Stage, RS, MA Cluster, Emerging Leader, Opportunity v2, Group Leadership, Fundamentals, chart/data infrastructure and relevant utilities as `KEEP / EXTEND / REPLACE / DROP`.
- Do not begin ranking redesign until the audit identifies what data/history are actually available and which fields need new point-in-time reconstruction.


## 2026-09-18 — Isolated Unified review GridView lab

- Repository: `Garrincha077/StockScout-Trend-Birth`.
- Branch: `feature/unified-review-grid-lab`.
- Branch head before this log update: `c062bf66885df1adbbdba1e93498817193616209`.
- Product decision: use Trend Birth as a completely isolated, **read-only companion** above the existing `Garrincha077/StockScout-Unified` production system. Unified remains the authoritative scan source and is not modified by this work.
- Safety boundary:
  - no writes to StockScout Unified;
  - no production Telegram token, Supabase key, broker credential or production secret;
  - no production deployment trigger;
  - lab workflow has `contents: read` only;
  - failure of the lab cannot change Unified scans, rankings, Pages, Telegram delivery or owner state.
- Added a read-only daily snapshot builder in `scripts/build_review_snapshot.py` that reads the active public Unified manifest and mode assets for Bottom Fishing, Next and Ryan Original, de-duplicates tickers, preserves source labels/ranks, and copies only the chart rows needed for the selected daily review set.
- Added an exploratory Oliver Kell-style review overlay: names already in the daily review universe with strongest available relative-volume evidence, default `RVOL >= 3.0x`, top 5. This is a review/discovery overlay, not a validated Trend Birth ranking model.
- Added mobile-first review UI under `lab/`:
  - one GridView for all selected tickers;
  - filters for All / Bottom / Next / Ryan / Kell 3x RVOL / Action;
  - ticker search;
  - lightweight canvas mini charts with EMA10 / EMA20 / SMA50;
  - tap/click/keyboard activation of a chart opens a larger ticker detail view;
  - detail view accepts an external per-ticker analysis JSON so a later ChatGPT Work step can write daily qualitative/technical/fundamental review without contaminating source scan data.
- Added `lab/data/analysis.example.json` as the analysis handoff contract and `lab/README.md` documenting the isolation boundary and local workflow.
- Added `.github/workflows/unified-review-grid-lab.yml` as a manual/PR-only validation workflow. It runs unit tests, builds a read-only snapshot from public Unified assets and uploads a short-lived artifact. It does not deploy or notify Telegram.
- Added `tests/test_build_review_snapshot.py` for relative-volume selection, Ryan buy-signal preference and Bottom structural-priority behavior.
- Validation performed locally before branch publication:
  - Python module compile passed;
  - 3 unit tests passed;
  - browser JavaScript syntax check passed.
- Behavior/ranking/scoring impact:
  - no existing Trend Birth ranking/scoring changed;
  - no Unified ranking/scoring or notification behavior changed;
  - the new code is an isolated review/data-presentation layer only.
- Important caveat: Next and Ryan daily selections can be reconstructed from public activated mode assets. The exact Bottom Telegram digest is generated from a private raw `bottom.json` GitHub Actions handoff, so the current lab Bottom selection is a transparent public-data proxy rather than a byte-for-byte recreation of the private Bottom Telegram selection. This must remain explicit until a safe read-only handoff is added.
- Main regression/methodological risks:
  - treating a single RVOL spike as a Kell-quality setup without context;
  - over-ranking names that are already extended;
  - confusing a review overlay with validated Trend Birth evidence;
  - drift between the public Bottom proxy and the private Bottom Telegram digest.

**Next logical step**
- Run the branch PR validation workflow against the live activated Unified public assets.
- If the artifact is correct, add a **Trend Birth-only preview publication path** so the user can open one mobile link to the GridView. Do not add production Telegram integration or modify Unified until the preview is stable and explicitly approved.


### 2026-09-18 — Lab live-data validation refinement

- Live isolated-branch GitHub Actions build succeeded against the activated Unified public scan for session `2026-09-17` / run `2026-09-17-eod-35287538852-1`.
- Fixed chart ingestion to support both public chart contracts:
  - Bottom's gzip chart-manifest/shard format;
  - Next/Ryan immutable JSON chart directories using `core.chartShards`.
- Verified chart coverage after the fix: **79/79** selected candidates in the broad RVOL test, and **78/78** after Kell-quality filtering.
- Refined the Kell overlay to reuse the transparent rules already exposed by Unified's Bottom screener:
  - Oliver Kell — Reclaim / Launch;
  - Oliver Kell — 52W Highs;
  - Oliver Kell — Bull Snort;
  - Oliver Kell — Doublers;
  - plus a user-requested liquid daily power-move overlay: `rvol_today >= 3`, `avg_dollar_volume_50d >= $20M`, price >= $5 and positive 1D return.
- The Kell scan now evaluates the full public Bottom pool (2,019 rows in the validated run), rather than only the normal top-25 review names.
- The raw RVOL-only trial surfaced extreme low-quality spikes (e.g. >100x RVOL), validating the need for liquidity/price sanity filters before ranking.
- Validated Kell daily-leader example from the live run: ACVA, SDGR, TWST, HELP, PUBM. Their matched Kell reasons are preserved in the detail payload; these are validation examples, not trade recommendations.
- The UI now labels this source simply as `Kell` and shows the matched Kell signals inside the ticker detail.
- Latest validation workflow remained read-only and green; no production Unified file, workflow, secret, Telegram path or deployment was changed.

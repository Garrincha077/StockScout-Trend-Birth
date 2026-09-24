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


## 2026-09-18 — Isolated Unified Review Grid Lab

- Branch: `feature/unified-review-grid-lab`.
- Draft PR: #1 (`lab: isolated Unified review GridView`).
- Safety decision: this repository is a read-only companion to `Garrincha077/StockScout-Unified`; no Unified writes, Telegram tokens, broker credentials, production Supabase keys, or production deployment permissions are used.
- Added `scripts/build_review_snapshot.py` to ingest only activated public Unified assets and aggregate Bottom Fishing, Next, Ryan Original and a separate Kell Daily Leaders overlay.
- Added responsive `lab/` GridView: all daily candidates appear in one chart grid; tap/click opens ticker detail. Current detail evidence includes EMA10/20 proximity, 50D and 30W slopes, RSI14, 20D/40D range-width proxy, current pivot HH/HL structure, close location, source badges and Kell confluence.
- Kell decision: Daily Leaders must pass a strict positive-day liquid `RVOL >= 3.0x` gate (`ADV50 >= $20M`, price >= $5), then pass chart-quality checks before inclusion; ordinary Kell saved-screen names do not back-fill the board. Unified Kell-style confluence remains supporting evidence/ranking context.
- AI/Work boundary: deterministic source and chart evidence lives in the snapshot; ticker-specific Work analysis is injected through a separate JSON contract and may add/override review state, preferred trade, QoQ fundamentals and risk notes.
- Workflow: `.github/workflows/unified-review-grid-lab.yml` has `contents: read` only and builds/tests an isolated artifact. No Pages or Telegram production integration is enabled.
- Validation: live public-data integration against Unified session `2026-09-17` is green. After the strict Kell chart-quality gate the lab produced 77 candidates with chart coverage for every selected name (77/77). Both `Unified Review Grid Lab` and `Cache Trend Birth Review Snapshot` checks pass; JavaScript syntax and snapshot invariants were checked from produced artifacts.
- Key implementation commits in this iteration include `403308e` (turning metrics + strict 3x gate), `2b3301a` (richer Grid/detail review), `c40e0b0` (post-chart Kell quality gate), and `d7fa026` (expanded Work-analysis handoff contract).
- Production behavior/ranking impact: **none**. `StockScout-Unified` and the Trend Birth `main` branch are unchanged.
- Main caveat: Bottom Telegram's exact digest uses a private Unified `bottom.json` Actions handoff; the lab currently reconstructs Bottom from activated public assets, so Bottom selection is a transparent proxy rather than a byte-identical copy of the private Telegram digest.

- Preview note: GitHub Pages build itself passed, but first-time Pages enablement failed because the GitHub App token cannot create the Pages site (`Resource not accessible by integration`). That failing workflow was removed. A separate Vercel project `stockscout-trend-birth-review-lab` was created; an initial deployment reached READY behind Vercel preview authentication. The feature branch contains the corrected Multi-hit / Kell 3x UI and cached snapshot; a permanent public/unprotected URL is not yet claimed as complete.

**Next logical step**
- Keep PR #1 draft. Use the isolated Vercel preview for functional UX review, then establish a stable public URL (either disable preview auth in Vercel or manually enable GitHub Pages once for the Trend Birth repo). Only after that should a later, separately approved change append the review link to production Telegram messages.


### 2026-09-18 — Oliver Kell Gap-Up added to Review Lab

- Added a separate `kell-gap` source/filter; it is not merged into the existing strict 3x RVOL Kell source.
- Canonical eligibility follows Kell's published Gappers screen: price > $20, 20-day average volume > 500k shares, and opening gap > 3%.
- Implementation is exact-bar based: the lab first makes a cheap read-only probe from the full public Unified Bottom universe, then loads OHLCV only for the top probe set and verifies today's open vs prior close plus actual 20D average volume.
- Daily best-of ranking is a second layer, separate from eligibility, using gap hold, close location, RVOL, and 50D/30W context.
- Latest verified Unified session produced 32 exact eligible gap names; the current top five were `TEM`, `SMCI`, `UMAC`, `COIN`, and `TWST`.
- GridView now includes `Kell Gap-Up`; ticker cards show gap %, detail shows gap % / held %, Avg Vol 20D, and a gap-specific preferred-trade state.
- Multi-hit continues to work across Bottom / Next / Ryan / Kell 3x / Kell Gap.
- Validation: Python unit tests pass, live snapshot build passes, chart coverage is 82/82 for the expanded daily board, and `node --check lab/app.js` passes on the built artifact.
- Production impact: none; all work remains on `feature/unified-review-grid-lab` in StockScout-Trend-Birth.


### 2026-09-18 — Nightly refresh and immutable archive verified

- Added a branch-local refresh trigger at `lab/refresh-trigger.txt`.
- Added immutable session archives under `lab/data/history/<sessionDate>.json`; `lab/data/latest.json` remains the moving latest pointer.
- GridView supports `?date=YYYY-MM-DD` and will load the immutable historical snapshot for that session.
- A manual smoke trigger on `feature/unified-review-grid-lab` completed successfully: unit tests passed, live Unified ingest passed, archive step passed, and the cache workflow correctly skipped the write because no newer activated Unified session was available.
- A ChatGPT scheduled task named `Trend Birth Refresh` is enabled for weekdays at 23:30 Europe/Zagreb. It only touches the Trend Birth lab feature branch trigger and verifies the resulting snapshot/archive; it must not modify Unified, Trend Birth main, Telegram, Supabase, or broker state.
- Remaining infrastructure item: stable public hosting. GitHub Pages cannot be first-enabled by the connected GitHub App, and the Vercel deployment connector currently errors on the deploy action even though the existing isolated Vercel project/read APIs work. The application/data pipeline itself is green.


## 2026-09-21 — Reliable review publication and delivery, phase 1

- Branch: `codex/reliable-review-publication`. Implementation commit: `9386eabf5f594982d7bf7de3a107305d321eec29` (follow-up hardening and docs remain on this branch).
- Changes: Immutable content-addressed snapshots; strict run/manifest validation; preserved date archives; snapshot-aware links without raw fallback; read-only preview workflow; example AI overlay removed from builds.
- Validation: 12 Python unit tests and 4 Node link tests passed; live build returned 82 candidates/82 charts for 2026-09-18; publication retry was a no-op; HTTP integration with Unified verifier passed.
- Scanner selection, rankings and scoring unchanged. No live Telegram message was sent; no production branch was merged or deployed by this implementation.
- Caveats: coordinated three-PR rollout required; ambiguous send needs manual reconciliation; per-mode metric separation and real dated AI review remain follow-up work.
- Next: review and activate in the order documented in `REVIEW_PUBLICATION.md`.


## 2026-09-22 — Candidate-only Oliver Kell scoring lab

- Branch: \`feature/kell-mcp-lab\`, based from \`feature/unified-review-grid-lab\`.
- Scope decision: Kell scoring is an **additive overlay on existing StockScout candidates only**. It does not create a new market-wide candidate universe, does not change source membership, and does not change the existing default ranking.
- Added \`scripts/kell_scoring.py\` with deterministic OHLCV proxies for 52W/New High, unusual volume, Bull Snort, 3M/6M momentum/Doubler, gapper, Strength on Down Day, EMA10/20 readiness, Wedge Pop, EMA Crossback, Base n' Break, tightening/contraction and breakout proximity.
- Added top-level candidate JSON fields including \`kell_score\` and a fully inspectable \`score_breakdown\`; unavailable criteria are excluded from the score denominator rather than silently treated as failures.
- \`Strength on Down Day\` uses SPY only as optional benchmark context. SPY retrieval is benchmark-only and does not alter candidate generation.
- GridView additions: Kell score badge, \`Kell >=60\` filter, Kell-score descending sort, and detailed criterion breakdown in ticker detail.
- Added isolated tests plus a GitHub Actions historical smoke step that enriches \`lab/data/history/2026-09-17.json\` and asserts candidate membership/order is preserved.
- Added \`docs/KELL_SCORING.md\` documenting definitions, weights, data provenance and caveats.
- Production impact: **none**. No merge to \`main\`, no Unified change, no Telegram change, no broker state change.
- Validation: branch CI is green on the implementation/fix commit: 18 Python tests passed; the 2026-09-17 historical Kell smoke scored all 82/82 existing candidates and preserved candidate membership/order exactly; top scores in that archived run were CMPS 57.6, SDGR 55.4 and VITL 54.3. The live public-data build for session 2026-09-21 produced 80 candidates with 80/80 chart coverage. Snapshot-link tests passed. A follow-up CI hardening step also adds `node --check lab/app.js` for GridView syntax.


## 2026-09-22 — Kell screens expanded to the full Unified candidate union

- Clarified product scope: every Kell screen now scans the deduplicated union of all candidates published by Unified across Bottom Fishing, Next and Ryan. Unified publisher semantics were verified: each mode's published `core.universe` is its candidate set (`counts.universe == counts.candidates`), so this does not introduce a new market-wide scan.
- Added a separate `kellCandidates` snapshot collection so full-union Kell matches do not alter or flood the ordinary Review Grid candidate set.
- Added separate full-union filters for 52W/New High, unusual volume >=2x, RVOL >=3x, Bull Snort, Doubler/3M-6M momentum, Gapper, Strength on Down Day, EMA10/20 readiness, Wedge Pop, EMA Crossback, Base n' Break, tightening and breakout proximity, plus Kell >=60.
- Added explicit `kell_rvol_3x` field. It is a screen flag, not an extra score weight, so the existing normalized Kell score remains comparable.
- The default All/Bottom/Next/Ryan board and existing source rankings remain unchanged. Production impact remains none; work stays isolated on `feature/kell-mcp-lab`.
- Validation: branch CI is green. On live Unified session `2026-09-21`, the deduplicated candidate union contained 2,683 tickers; 2,174 matched at least one Kell screen. The ordinary Review Grid remained 80 candidates with 80/80 chart coverage. 18 Python tests, historical 2026-09-17 smoke, snapshot-link tests and GridView JavaScript syntax all passed.

- Follow-up benchmark validation: `Strength on Down Day` now reconstructs SPY from Unified's embedded RS ratio (`RS = stock / SPY * 100`) rather than requiring SPY to be a candidate chart. Live session 2026-09-21 implied SPY return about +1.55%, so the screen correctly returned 0 names on that up-market day. Full chart coverage remained 2,683/2,683. Screen counts on that session: 52W 122; unusual volume >=2x 62; RVOL >=3x 15; Bull Snort 15; Doublers 218; Gappers 110; EMA Ready 385; Wedge Pop 14; EMA Crossback 243; Base n' Break 12; Tightening 2,042; Near Breakout 347.


## 2026-09-22 — Kell v2 grounded in Victory in Stock Trading

- Reviewed Oliver Kell's *Victory in Stock Trading* and replaced the broad v1 pattern proxies with `kell-overlay-v2-pdf`.
- Split momentum into `kell_momentum_3m_50` (3M +50%) and the true `kell_doubler_6m` / compatibility `kell_doubler` (6M +100%).
- Reworked Cycle of Price Action as stateful sequence logic: Wedge Pop = first recapture of a tight 10/20 EMA cluster after working lower; EMA Crossback = first retest after a recent Wedge Pop; Base n' Break = longer EMA-supported contraction followed by breakout.
- Tightening now requires true-range contraction plus volume dry-up or inside-bar evidence; added a separate TTFTL relative-weakness warning proxy.
- Added book-aligned name-selection context using only fields already present in Unified: price/liquidity, RS rank, weekly 10EMA, revenue YoY, EPS YoY and fundamental support fallback.
- Growth context is conservative: both revenue and EPS must be >=25% when both are known; a single known metric must be >=25%; `fundamentalSupport` is only a fallback when numeric growth is unavailable.
- Added RS Divergence from reconstructed point-in-time SPY history, broad Gapper vs stricter Buyable Gap proxy, and a small `kell_focus` research shortlist.
- `kell_focus` keeps individual screen lists intact and combines name-selection, leadership/growth context, and a core entry setup or high-quality gap proxy. It is explicitly a reproducible research proxy, not a claim to duplicate a proprietary Kell list.
- Commits: `849105a` (PDF cycle alignment), `b68fadd` (growth/RS context), `adc210d` (Kell Focus and stricter growth logic), plus docs commit `1191b8f`.
- Validation run `35776465023` completed successfully: 26 Python tests passed, historical 2026-09-17 membership/order remained unchanged, snapshot-link and JS syntax tests passed, and live full-Unified build passed.
- Live session 2026-09-21: 2,683 Unified candidates, 2,683/2,683 charts, 1,982 names hit at least one v2 screen. Key counts: Focus 6; Growth 264; RS>=90 330; 3M+50 139; 6M Doubler 131; Bull Snort 25; Buyable Gap 10; RS Divergence 500; Wedge Pop 111; Crossback 15; Base n' Break 51; Tightening 98.
- Focus list on that session: AMD, SLF, ARM, INTC, MXL, TTMI.
- Precision improvement against v1 on the same live session: Tightening 2,042 -> 98; EMA Crossback 243 -> 15.
- Production impact remains **none**. Work stays isolated on `feature/kell-mcp-lab`; Unified/main/Telegram/broker state were not changed.


## 2026-09-22 — Kell v4 separates discovery screens, stock stage and setups

- Branch: `feature/kell-mcp-lab`. Production `main`, StockScout Unified, Telegram and broker state remain unchanged.
- Product/data-contract decision: **SCREEN != STAGE != SETUP**.
  - **Screen** answers why a stock was discovered.
  - **Stage** publishes one primary current Kell Cycle-of-Price-Action state plus confidence/evidence.
  - **Setup** publishes actionable pattern/readiness flags that may coexist with the stage.
  - **Context** carries supporting liquidity, growth, RS and higher-timeframe evidence.
- Model version: `kell-overlay-v4-screen-stage-setup`; compact browser schema: `kell-compact-v2`.
- Added disjoint `kellScreens`, `kellSetups`, `kellContext` arrays and a `kell_stage` object. `kell_cycle_stage` remains a compatibility alias.
- Current primary stages: `wedge_pop`, `ema_crossback`, `base_n_break`, `trend_ema_support`, `downtrend_repair`, `transition`, `unavailable`.
- GridView now has visibly separate **Screens / Stage / Setups / Context** filter groups. Cards show Stage and Setup separately; ticker detail shows discovery screens, stage, setups, context and stage confidence.
- Score remains a secondary ranking aid, but now exposes separate `discovery`, `stage`, `setup` and `context` components rather than hiding the dimensions in one number.
- CI hardening updated the compact-data validator to enforce the v4 contract and mutual separation of the three list dimensions.
- Full live validation on Unified session `2026-09-21`: **2,683** deduplicated Unified candidates, **2,683/2,683** chart coverage, **2,063** published Kell matches. No candidate-universe expansion occurred.
- Live discovery counts: 52W 3; unusual volume >=2x 62; RVOL >=3x 15; Bull Snort 20; 3M +50% 139; YTD Doublers 39; Gappers 58; Strength on Down Day 246; RS Leader 330.
- Live setup counts: Buyable Gap 6; Wedge Pop 111; EMA Crossback 15; Base n' Break 51; Tightening 98; Near Breakout 347.
- Live primary-stage counts: Wedge Pop 111; EMA Crossback 15; Base n' Break 49; Trend/EMA Support 285; Downtrend/Repair 1,091; Transition 512.
- Real-candidate checks validated the intended separation: GRAL = Base n' Break stage with several discovery screens and two setups; WBD = Wedge Pop stage with multiple discovery/setup hits; DELL = strong discovery/context evidence but Trend/EMA Support stage and no active setup.
- GitHub Actions run **#111** completed green end-to-end: Python tests, historical overlay smoke, snapshot-link tests, JS syntax, live Unified rebuild, compact v4 build/validation, preview-data publication and artifact upload.
- Important finding: `downtrend_repair` is currently broad (1,091 names) because it intentionally starts as a simple bearish 10/20 EMA structural bucket. It should be refined before treating it as a precise Kell cycle stage.

**Next logical step**
- Extend the stage engine with transparent, book-grounded proxies for **Reversal Extension**, **Exhaustion Extension** and **Wedge Drop**, then retest the full 2,683-name Unified pool and compare stage-distribution precision before/after. Keep the discovery screens unchanged while doing this.


## 2026-09-22 — Kell full Cycle stage milestone

- Continued the v4 stage engine on `feature/kell-mcp-lab` without changing Unified candidate generation, production `main`, Telegram or broker state.
- Added transparent, book-grounded stage proxies for the three missing outer Cycle phases:
  - **Reversal Extension** — downside extension from 10EMA + higher-timeframe support proxy + bullish reversal bar + elevated volume;
  - **Exhaustion Extension** — fresh high materially extended from 10EMA, but only inside an established rising 10/20 EMA / positive intermediate-trend context and with a blowoff clue;
  - **Wedge Drop** — recent Exhaustion Extension followed by loss of the 10/20 EMA cluster.
- These are explicitly **lab proxies**, not claimed Kell constants. The numerical gates are documented in `docs/KELL_SCORING.md`.
- Added dedicated Stage filters for Reversal Extension, Exhaustion Extension and Wedge Drop. They remain separate from discovery Screens and entry-oriented Setup filters.
- Added regression tests for all three new stage events. A first Exhaustion implementation exposed a precision problem: rebound names could qualify merely by being far above a depressed EMA. Reproduced that behavior, required established uptrend context, updated the synthetic tests, and re-ran the live pipeline.
- BEFORE -> AFTER on live Unified session `2026-09-21`:
  - generic Transition: **512 -> 505**;
  - generic Downtrend/Repair: **1,091 -> 1,087**;
  - new Reversal Extension: **4**;
  - new Exhaustion Extension: **6**;
  - new Wedge Drop: **1**;
  - Wedge Pop **111**, EMA Crossback **15**, Base n' Break **49**, Trend/EMA Support **285** stayed unchanged.
- The first live Exhaustion proxy found 12 names. Requiring rising 10EMA > 20EMA plus positive prior intermediate trend reduced this to **6**, while preserving plausible examples such as AMD and ARM.
- Real-stage spot checks after the refinement: VKTX / THO / ESAB / DNLI = Reversal Extension; AMD / ARM / AMRX / PRTH / FAC / VITL = Exhaustion Extension; TARS = Wedge Drop. These are model classifications, not trade recommendations.
- Discovery-screen and setup counts were unchanged by the stage refinement, confirming that stage work did not contaminate discovery logic.
- CI workflow now has branch-level concurrency with `cancel-in-progress: true` so future rapid development pushes do not waste multiple simultaneous full Unified rebuilds.
- GitHub Actions run **#120** completed green end-to-end: unit tests, historical Kell smoke, snapshot-link tests, JS syntax, live Unified rebuild, compact v4 validation, safe preview-data publication and artifact upload.
- Full live pool remained **2,683** Unified candidates with **2,063** published Kell matches; no new market-wide universe was introduced.

**Next logical step**
- Make stage coverage fully independent from discovery publication: preserve stage metadata for all **2,683** existing Unified candidates, while keeping `Kell Hits` as a separate discovery/setup/context subset. Then refine the broad `downtrend_repair` bucket using recent-cycle history rather than adding new discovery screens.


## 2026-09-22 — Review chart readability and full Kell chart availability

- Branch: `feature/kell-mcp-lab`; no production Unified, Telegram or broker behavior changed.
- Reproduced the `Chart data unavailable` problem in full Kell filters. Root cause was not missing Unified OHLCV: live metadata showed **2,683/2,683** chart coverage, but the compact browser payload intentionally stripped `chartBars` from all **2,063** Kell matches. Only tickers also present on the small ordinary Review Grid received chart rows via the client merge.
- Fixed the data path by publishing lazy OHLCV chart shards from the already-loaded Unified candidate charts. Compact schema is now `kell-compact-v3`; chart schema is `kell-chart-shard-v1`.
- Live session `2026-09-21`: **2,063/2,063** Kell matches have chart-shard coverage, **535,895** total bars in **43** shards. The UI loads only the shard needed by a visible/detail ticker and caches it client-side.
- Added explicit chart price scale on the right and three date labels across the x-axis. Detail charts also show EMA10 / EMA20 / SMA50 and session count.
- Found mixed date encodings in real Unified charts: some rows use ISO dates and some use Unix epoch seconds. The axis formatter now handles both; e.g. GRAL's epoch range resolves from 2025-09-09 to 2026-09-21.
- Added compact-builder tests for normalized chart rows and complete shard coverage. CI run **#125** passed Python tests, historical Kell smoke, snapshot-link tests, GridView JavaScript syntax, full live Unified rebuild, compact/shard validation, publication and artifact upload.
- Vercel live checks on the latest preview returned HTTP 200 for the app, `kell-compact-v3`, shard 000 and shard 042; both the first candidate (GRAL) and a final-shard candidate (VTOL) returned 260 bars.

**Next logical step**
- Add optional user-selectable chart windows (for example 3M / 6M / 1Y) only if the denser axes prove useful in review; keep the default lightweight and avoid adding chart-library dependencies unless canvas rendering becomes a real limitation.


## 2026-09-22 — Universe-first hierarchical filtering

- Branch: `feature/kell-mcp-lab`; production Unified/Telegram/broker behavior unchanged.
- Changed the GridView filter model from one mutually-exclusive filter into two independent axes:
  - **Universe** = `All / Bottom / Next / Ryan`;
  - **secondary filter** = Screen / Stage / Setup / Context / review filter.
- A secondary Kell screen now always intersects the selected universe instead of replacing it. Example on live `2026-09-21`: global Bull Snort = 20; Bottom -> Bull Snort = 18; Next -> Bull Snort = 13.
- Switching universe preserves the selected secondary filter, so the user can compare the same screen across Bottom / Next / Ryan without reselecting it.
- Filter-button counts are recalculated inside the selected universe, not from global Kell counts.
- Added a dedicated `No filter` state. `Kell Hits` moved out of Universe and is now a secondary screen-like filter.
- The status line now shows the selected universe and its full candidate count from Unified metadata: Bottom 2,045; Next 1,989; Ryan 1,989 on the validated session.
- Universe and secondary-filter active states are visually distinct.
- Added browser-model regression tests for the hierarchy and a compact-data test ensuring mode universe counts survive publication.
- GitHub Actions run **#145** passed Python tests, browser-model tests, JavaScript syntax, historical Kell smoke, full live Unified rebuild, compact/shard validation, publication and artifact upload.
- Latest Vercel preview was live-checked: HTML, app JS and compact data all returned HTTP 200; hierarchy controls and universe-specific intersection logic are present.

**Next logical step**
- If desired, allow multiple secondary screens to be AND/OR-combined inside the selected universe. Keep single-screen selection as the default because it is simpler and clearer.


## 2026-09-23 — Kell Gold Set + calibration harness

- Branch: `feature/kell-mcp-lab`; production Unified EOD / Trend Birth, Telegram and broker behavior remain unchanged.
- Added a persistent human-reviewed calibration set in `lab/data/kell-gold-set.json` with point-in-time `VALID / BORDERLINE / FALSE_POSITIVE` semantics and reason codes. The seed set currently contains **21 reviewed labels across 2 sessions**: **18 VALID** and **3 BORDERLINE**.
- Added `scripts/kell_gold_set.py` to compare the signal recorded at review time (BEFORE) with the same ticker/session in current or recovered point-in-time Kell archives (AFTER). The report is written to `lab/data/kell-gold-set-eval.json`.
- Metrics are reported overall and per signal bucket: reviewed/evaluated count, added/lost predictions, accepted precision, strict VALID precision, positive recall, weighted quality, fixed/unresolved false positives and hard VALID regressions.
- Historical compatibility matters: recovered `kell-score-history-v2` archives are columnar rows, while newer archives are dictionary-based. The first CI run exposed this mismatch with `AttributeError: 'list' object has no attribute 'get'`; the evaluator was fixed to inflate v2 rows via the archive `columns` definition and a dedicated regression test was added.
- Point-in-time archives now preserve Screen / Setup / Context arrays for future calibration while still omitting chart bars. Older archives remain stage-evaluable and report unavailable dimensions honestly rather than treating them as negatives.
- Real 2026-09-22 candidate review seeded setup labels including HALO Base n' Break, KLIC and GRMN EMA Crossback, SEPN Wedge Pop, and BORDERLINE execution-quality examples ONON buyable gap plus NX/SXT Wedge Pop. No FALSE_POSITIVE label was invented where chart review was not sufficiently clear.
- Final Gold Set evaluation: **21/21 evaluable**, **0 unavailable**, **0 lost**, **0 added**, **0 hard regressions**, accepted precision **100%**, strict VALID precision **85.7%**, weighted quality **92.9%**. Wedge Pop is the main quality-calibration bucket in the seed sample: 1 VALID + 2 BORDERLINE; Buyable Gap has 1 BORDERLINE.
- Regression state remained clean on live session `2026-09-22`: **2,693** Unified candidates, **2,085** Kell matches, full **2,693** chart coverage; signal validator reported **0 hard errors**, **0 screen mismatches**, **0 stage mismatches**, **0 layer overlaps**.
- Core setup contract counts remained unchanged: Base n' Break 48/48 strong, Buyable Gap 4/4 strong, EMA Crossback 61/61 strong, Wedge Pop 144/144 strong. Gold Set labels are deliberately a stricter human calibration layer and do not automatically change production proxy thresholds.
- Forward-validation guard still behaves correctly: 10 point-in-time score snapshots are available, but 5/10/20/40/60/120-day comparisons remain ineligible until >=99% outcome coverage exists; no premature performance conclusion is emitted.
- GitHub Actions run **#222** completed green end-to-end after the archive compatibility fix: unit tests, historical smoke, browser tests, live Unified rebuild, compact validation, signal validation, calibration report, Gold Set evaluation, forward validator, BEFORE/AFTER spot check, publication and artifact upload all passed.

**Next logical step**
- Expand the Gold Set across additional independent sessions and deliberately hunt for confirmed `FALSE_POSITIVE` / false-negative examples, especially Wedge Pop and Buyable Gap. Only after that evidence exists should a proxy threshold or ranking weight be changed.

## 2026-09-24 — Kell Sequence Engine / What Changed in the Cycle

- Branch: `feature/kell-sequence-engine`; draft PR #16 targets `feature/what-changed-today`. Stable Unified EOD / Trend Birth publication, Telegram and broker behavior remain unchanged.
- Replaced score-delta-centric “Changed” detection with a sequence/location review model. Large `kell_score` or readiness jumps remain diagnostics but no longer create a change by themselves.
- Review changes are separated into **Discovery**, **Stage**, **Setup actionable**, plus explicit **risk/cycle-failure** priority. Setup events rank above discovery-only changes.
- Added sequence-aware events: Wedge Pop appeared, FIRST actionable EMA Crossback, LATE EMA retest, Base n' Break with EARLY / MATURE / LATE-CYCLE context, first/repeated Exhaustion Extension, and Wedge Drop structure failure.
- EMA Crossback now prefers the chart-derived `ema_retest_state` produced from the OHLCV Kell scorer. This prevents incomplete daily snapshot history from overriding the first-vs-late retest determination.
- Auxiliary `transition / trend_ema_support / downtrend_repair` flicker no longer counts as a review-worthy Kell stage change unless price enters an explicit Cycle-of-Price-Action event.
- Change cards now lead with cycle event and change layer, show stage transition / sequence trail, FIRST vs LATE retest, cycle maturity, and natural invalidation in ATR. A >=3 ATR “risk too wide” gate is a **StockScout review proxy**, not a Kell-published constant.
- Point-in-time Kell archives now preserve stage basis and structural-risk ATR for future sequence validation. Browser history loading supports recent JSON archives and older columnar gzip/base64 archives.
- Market context is carried read-only from the hash-verified Unified core. If upstream exposes exact QQQ-vs-20EMA, the UI uses it. Otherwise `under_pressure / correction` is labeled explicitly as **Unified fallback**, not presented as Kell’s exact QQQ/20EMA rule.
- Real BEFORE -> AFTER check on the same 2026-09-22 -> 2026-09-23 Kell population: old score-centric detector flagged **63** names; sequence detector flagged **229** = **58 setup**, **18 risk**, **7 stage**, **146 discovery**. Sorting keeps actionable/risk events ahead of discovery.
- Real examples demonstrate the intended change: WDC became FIRST ACTIONABLE CROSSBACK with only **+1.6 Kell / +6.4 readiness**; HBM did so with **0.0 Kell / +6.7 readiness**. Conversely FRO / CMPS / WIX surfaced as **STRUCTURE FAILED · WEDGE DROP**, and SNX / VKTX as **FIRST EXHAUSTION EXTENSION**, events the old positive-score-jump logic did not prioritize. Full 2026-09-23 chart data showed structural invalidation about **1.05 ATR WDC**, **0.42 ATR HBM**, and **1.01 ATR TRT**.
- Old-only examples FRSH and ABSI were removed from the change view: they had large score/readiness increases but only auxiliary-stage movement and no new actionable Kell setup.
- Validation: PR CI **Unified Review Grid Lab #299** completed green end-to-end; **Validate Trend Birth Review Snapshot #77** also completed green. Unit tests, historical Kell smoke, browser-model tests, JS syntax, live read-only snapshot build, compact validation, source-identity validation, signal validation, Gold Set evaluation, forward validator and existing Kell v5 BEFORE/AFTER smoke all passed. PR publication step was correctly skipped.


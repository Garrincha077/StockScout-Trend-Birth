# StockScout Trend Birth — Persistent Project Log

## 2026-10-25 — Market Thermometer: pet jednakih temperaturnih zona (prva verzija)

- **UI:** kartice Quality breadth, pressure, 4/4 i trajnosti dobivaju semantičku nijansu po **povijesnom temperaturnom percentilu**; 0–<20 tamno zeleno (vrlo hladno), 20–<40 svijetlo zeleno, 40–<60 žuto, 60–<80 narančasto, 80–100 crveno (pregrijano). Za preostale dinamičke kartice boje ne predstavljaju temperaturu.
- **Formule:** Market Thermometer 0–100 = aktivno ponderirani PIT percentili breadth (40), pressure (30), 4/4 (20), 10-EOD persistence (10), s midrankom i najviše 252 **prethodne** stvarne EOD točke. Svaki faktor zahtijeva ≥12 ranijih valjanih podataka; sva tri core faktora su obvezna, nespremna persistence se izostavlja i težine se normaliziraju. To je opis relativnog stanja StockScout setupa, ne tržišna valuacija, vjerojatnost rasta ili trading signal.
- **Dinamika odvojena:** 5-EOD velocity (45), dvije nepoklopljene 5-EOD brzine za acceleration (30) i matched-quality delta (25) daju normaliziranu skalu −100…+100, uz ±30 za promjenu i potvrdu 2 susjedna EOD-a; usporedni flow ne sudjeluje pri preklapanju <95%.
- **Povijest:** zaseban termalni SVG 0–100 s pet zona, datumska kontrola i tablica sirovo/PIT percentil/aktivna težina/doprinos. Odabrani stvarni EOD datum i raspon sinkronizirani su s Composite grafom; za ETF proxy sinkronizacija je onemogućena i objašnjena. Prazni trgovački dani nisu interpolirani. Komponenta čita postojeći kompaktni JSON, bez novih skenova, troškova ili promjene Composite formule.
- **Zasad:** arhiva ima 20 stvarnih EOD dana (2026-09-24…2026-10-23), samo osam preliminarnih temperaturnih opažanja (od 2026-10-12); 2026-10-23 iznosi približno 33,92/100 (hladno), bez dovoljno povijesti za persistence percentil. Srednja pouzdanost tek nakon ≥60, duža nakon ≥120 prethodnih opažanja. Nedostaju 15. i 19. 10., nema backfilla.
- **Provjera:** Node unit/regression tests/trend-birth-heat.test.cjs; PR CI i live Vercel vizualni pregled obavezni prije proglašenja isporučenim.

This file is the durable handoff for `Garrincha077/StockScout-Trend-Birth`.

Update it after every meaningful code, workflow, data-contract, research-methodology or product-architecture change.

## 2026-10-25 — Disable stale EOD rewrite caching after Composite history release

- The Composite history PR #65 was merged to the active Review Lab branch as `9080d3ea3730b5a96c5610ef4baaf1c3cbfc4d84`, with validated EOD and ETF OOS traces. Browser check detected Vercel's `/data/` external rewrite still proxying old 7.9 KB JSON even though GitHub Raw held the 205 KB current version.
- Scope-limited remediation: configure `x-vercel-enable-rewrite-caching: 0` for `/data/(.*)` while preserving browser no-store. This follows official Vercel external rewrite guidance; a regression test enforces the header. No change to StockScout trading logic or EOD snapshots.

## 2026-10-24 — Production EOD verification for StockScout Intelligence v1

- **Git commits/PRs:** Review Lab #51 merged as `3bcfc2bb7822009b2f238ed8d445d5095bbbc3f5`; Unified Telegram #112 merged as `c3bfbe93810cb5295c56b462d7b0a0350dce3b70`. Production Review EOD emitted `2261cdf6885a958e129ffef782e25bff3c579f5f`.
- **CI:** Review PR run `40118997516` = success; Unified PR run `40118998453` = success. Production EOD run `40119600553`: primary `build` job success, including monthly stage extraction, Telegram no-send payload, publication alignment and Git push. Separate `historical_calibration` may still be running at this checkpoint.
- **Deployed:** Vercel deployment `dpl_5cv2GGU3faH2s2i5MmtiGae5PRkn` READY on active production branch. Production root and compact EOD JSON return HTTP 200; frontend renders real opportunities.
- **Archive:** immutable 20 observed sessions 2026-09-24 through 2026-10-23; five September sessions, fifteen October. Cross-checked every daily stage count, evaluated, unavailable and scope against compact quality-history; then validated ticker membership across all selected **20 D, 5 W and 2 M buckets × five stages = 135 no-difference segment checks**.
- **EOD:** session 2026-10-23, run `2026-10-23-eod-40042215150-1`, 2,614 evaluated, one unavailable. Stages [2222,182,47,58,105]; 3+ share 6.24% and P37 (only 19 earlier daily baselines). 2,602 tickers comparable to 2026-10-22; 144 upgrades, 93 downgrades, 60 new 4/4, 16 to-ready. These are descriptive evidence-defined label changes, not causal investment edge.
- **Live browser verification:** Today's panel displays real metrics, D/W stacked chart still renders. Clicking Oct23 4/4 yields 105 ticker names. Clicking W 2026-10-19..25 yields 218 unique tickers across 417 ticker-days. Clicking AZTA reveals 20 observed daily stages, no invented unavailable state.
- **Notification:** `trend-birth-alerts.json` contains one `intelligence-eod` message, and Unified receiver now accepts it in legacy and weekly-v2. Direct Telegram sending **not yet observed**; check next scheduled sender run, delivery ledger and possible flood from existing per-ticker trigger messages.
- **Next:** verify uninterrupted next-session EOD append (without truncation), scheduled Telegram dispatch, optionally reduce message multiplicity and benchmark total GitHub/Vercel checkout time before touching raw history. No raw archives deleted.

## 2026-10-24 — StockScout Intelligence v1: ticker-stage history, opportunities, drill-down

- **Scope:** user-approved stage-level exploration without scanner rewrite: all 0/4–4/4 stages for the full verified Unified + tracked watchlist universe; compact daily opportunities; historical ticker membership; individual journey; existing Telegram no-send EOD enrichment.
- **Data model:** new `scripts/trend_birth_intelligence.py` extracts every EOD ticker from `trendBirthCandidateIndex`, verifies `trendBirthRadar.stageCounts`, tracks unavailable separately, encodes ten disclosed checks into a bitmask and stores chronological monthly shards under `lab/data/trend-birth-ticker-history/YYYY-MM.json`. Month shards retain all dates; existing raw point-in-time history can backfill only observed historic data, skipping snapshots without the radar schema. Old month points are reused when raw history expands or changes; conflicting same-date values fail rather than overwrite.
- **Transition method:** daily `trend-birth-intelligence-v1` summary compares only tickers evaluated in both consecutive saved scans. Stage jumps 2→4 count as upgrades/new 4/4; new coverage and unavailable names are not transitions. Includes a baseline-only flag, counts, source date/run, a small evidence-grounded opportunity shortlist, and full new-4/4 ticker list for digest.
- **Dashboard:** lightweight Today's Opportunities panel loads before raw Review payload; reconciles to Review date/run/denominator when loaded. D/W/M stacked 100% chart and 1M/3M/1Y/5Y/All plus zoom remain unchanged. Chart click lazily loads archived months, checks the selected bar's total ticker-days, provides filterable 0–4/4 ticker membership and per-ticker stage journey. No historical list is guessed when shards are absent.
- **Telegram:** existing `scripts/build_trend_birth_alerts.py` receives optional `--intelligence`, checks date/run/count agreement and generates one `intelligence-eod` message in the existing no-send JSON. This change itself does **not** send messages; existing Unified sender rejects unknown message kinds; companion StockScout-Unified PR #112 explicitly allows `intelligence-eod` in legacy and weekly-v2, preserving shadow and the delivery ledger. It must merge before producer PR #51. No EOD message when sparse legacy alert baseline has no prior candidate, preserving sender baseline validation.
- **Cost:** same nightly workflow; month shards are included in existing atomic publish (backup/restore after Git checkout); Vercel build continues to ship static code only and fetches small JSON on demand; monthly archive excluded from GitHub diagnostic artifact.
- **Verification:** in-memory Python integration for stage extraction + Telegram composition passed. Additional Python/Node tests in repo; full CI and first published EOD are required before calling feature production-verified.
- **Next:** confirm PR/CI, first monthly shard, compact EOD summary on production, Telegram external sender recognition and mobile lazy-load behavior. Avoid synthetic pre-radar history.

## 2026-10-24 — Slim EOD diagnostic artifact and daily-history integrity guard

- **Read-only archive audit:** Review `history/` 25 files / ~1.89 GiB, `snapshots/` 61 / ~4.85 GiB; Kell `kell-history/` 21 / ~0.38 GiB and `kell-snapshots/` 53 / ~0.82 GiB. Of those, 23/25 Review date archives share the exact Git blob with a snapshot and 21/21 Kell date archives do too. Git SHA deduplication already prevents redundant object storage; working-tree nominal sizes must not be confused with Git pack or GitHub Actions artifact sizes.
- **Non-destructive preservation:** `snapshot-loader.js` addresses immutable run snapshots/date archives; `kell_gold_set.py` can re-score historical raw evidence. Raw archives remain untouched in Git, without history rewriting, file removal, new data service or new workflow.
- **Vercel already optimized:** `lab/build-vercel.mjs` excludes archived `lab/data` from `dist`; deployed UI fetches public JSON via GitHub Raw rewrite. No redundant Vercel changes.
- **Cost fix in existing daily job:** `Upload review lab artifact` previously uploaded all of `lab`; one verified completed run `40106259332` stored a compressed **2,919,486,005-byte** 7-day artifact. Keep the artifact name and today's snapshot/charts/scripts, but exclude 6 archive directories with supported `actions/upload-artifact` negative glob rules. This does **not** shrink previous artifacts or Git history; measure actual savings on the next completed job.
- **Fail-closed EOD contract:** `scripts/trend_birth_quality_history.py` adds optional `--latest` to compare full verified stage counts, source run ID, scope and date of `latest.json` to the final retained compact daily point. Both existing publication-time invocations supply the flag. Missing radar, mismatched/stale latest, or inconsistencies fail before writing misleading history. Old radar-less dates remain absent; genuine historic points stay immutable.
- **Regression plan:** Python tests for matching, missing radar, stale and conflicting latest; YAML parse checks for two guarded invocations and archive exclusions. CI confirmation required on the topic PR. Next verify artifact size and a 21st legitimate daily session, then perform *separate* recoverable backup/backtest design before requesting deletion approval.

## 2026-10-24 — Durable HANDOFF.md for cross-chat continuity

- Verified GitHub PR #48 / production feature commit `777c5a2f503105efce527a1260cfe58ea3d92277` and both required CI jobs (`build`, `historical_calibration`) green on Actions run `40106259332`.
- Verified Vercel READY for the feature commit and for a subsequent latest-data publication `853c193346f7c51bfd99d8fcdedc56a6cf8d7ceb`. The compact stage-breadth JSON still contains 20 verified daily sessions ending on 2026-10-23.
- Created root `HANDOFF.md`: explicit active production branch, stable dashboard link, stage-history schema/formulas, storage threats, no-delete constraints, remaining tasks, smoke checks and resume instructions. Updated `AGENTS.md` to require refreshing **both** current-state handoff and append-only project log after meaningful changes; linked handoff from `README.md`.
- **Documentation only**: no scanner, alert, order, chart logic, storage cleanup or workflow changes. Deployment may still occur automatically on a docs-only Git commit; check state if needed.
- Next: Android/mobile production smoke test; observe the next genuine EOD retaining 20+ earlier sessions; audit and archive massive raw histories only after point-in-time/backtest and recoverable backup review.

## 2026-10-24 — Permanent compact Trend Birth setup history, D/W/M and 1M/3M/1Y/5Y/All

- Topic branch: `codex/trend-birth-dwm-permanent-history-20261024`, based on the deployed `feature/unified-review-grid-lab` branch. Commit SHA: recorded in GitHub PR history.
- The breadth chart offers daily (D), ISO Monday–Sunday weekly (W) and calendar monthly (M) intervals plus independent 1M/3M/1Y/5Y/All historical windows. The original five-level 100%-stacked red-to-green bars, 25/50/75/100% vertical close-up zoom, selectable stages, count details and interval-specific historical percentiles remain.
- Weekly/monthly stage shares are weighted by each archived day's evaluated universe: sum(stage counts) / sum(evaluated counts). Their counts represent *ticker-days*, not distinct tickers, and the UI reports the number of actual daily observations and flags edge periods partially covered by the archive.
- Derived W/M series and selected horizontal history windows exist **only in the browser**. There is no W/M persistence, server storage, additional scheduled scan, snapshot clone or added deployment. All retained daily points remain the source; long ranges are no longer truncated to the most recent 45 sessions.
- Hardened `scripts/trend_birth_quality_history.py` to merge previously validated historical points with immutable daily radar archives, preserving past compact observations even if old 80–100 MB raw snapshots are eventually moved out of Git. It explicitly rejects conflicting rewrites and cross-universe merges. Existing pre-radar dates are never invented or backfilled.
- Affected: `lab/index.html`, `lab/app.js`, `lab/styles.css`, `lab/trend-birth-quality.js`, `scripts/trend_birth_quality_history.py`, `tests/trend-birth-quality.test.cjs`, `tests/test_trend_birth_quality_history.py`.
- No changes to scanner membership, radar thresholds, Telegram sending, broker integration or costly historical snapshot retention workflows. The archive size and duplicate large raw JSON directories remain an **independent** storage concern; do not delete point-in-time research archives without dependency review, a recoverable backup and explicit user authorization.
- Regression validation: test weighted aggregation and stack conservation, calendar boundaries and leap year, range retention, selective chart controls, old-archive removal resilience and collision safety.
- Caveat: Weekly/monthly percentiles initially have small samples, and any incomplete final aggregation period is provisional. No daily data before the first verified radar reading is claimed.
- Next: verify production Vercel dashboard and CI after merge; separately audit large raw archive deduplication and Git history size before undertaking any cleanup.

## 2026-10-24 — Stacked Trend Birth breadth, selectable colours, stepped zoom and historic percentile

- Topic branch: `codex/trend-birth-stacked-breadth-zoom-20261024`, based on production `feature/unified-review-grid-lab` at `10193975ef9cdecbb2140e783d7790125204bc2b`; implementation SHA is the commit containing this entry.
- Replaced the single-stage history bars with **one true 100%-stacked bar per archived session**: 4/4 green at the bottom, then 3/4 light green, 2/4 yellow, 1/4 orange, 0/4 red at the top.
- Stage checkboxes and two presets colour-highlight any subset while dimming unchecked segments without rebasing their percentages. The original 100% denominator stays intact even when all stages are muted.
- Zoom buttons show **0–25%, 0–50%, 0–75% and 0–100%**. Cropping is from the bottom of the full stack so high-quality small shares are readable, and underlying stage percentages remain unchanged.
- Added a point-in-time percentile card for any single stage, combined 3/4+4/4, or the selected subset. The latest daily percent is compared only to earlier archived sessions using a midrank for ties; full history is used for percentile even when bars display the most recent 45 sessions.
- Added per-day interactive count/percentage inspection and explicit all-stage/unavailable denominators; old immutable archives remain authoritative. No scanner thresholds, membership, signal definitions, Telegram format, risk settings or source schemas changed.
- Affected: `lab/index.html`, `lab/app.js`, `lab/styles.css`, `lab/trend-birth-quality.js`, `tests/trend-birth-quality.test.cjs`. Added validation for composition integrity, four zoom levels, tie-aware percentile and independent historical denominators.
- Risk: a high percentile of 0/4 is **not bullish**. With only 20 available sessions initially, a percentile is a descriptive rank, not a statistically robust market forecast. Close-up intentionally crops higher levels of the stack.
- Next: confirm browser/mobile rendering, GitHub regression CI and Vercel deployment; add additional genuine daily history over time.

## 2026-10-24 — Historical setup quality as a percentage (fixed 0–100% scale)

- Topic branch: `codex/trend-birth-history-percent-axis-20261024` based on production `feature/unified-review-grid-lab` at `5632cdcdbe6e08ca995d9556b08e3e3d8cbafc9a`; implementation is the commit containing this entry.
- Changed the selectable historical 0/4–4/4 and combined 3/4+4/4 graph from autoscaled absolute counts to percentage of each session's **evaluatedCount**. The Y axis is explicitly and permanently marked 0, 25, 50, 75 and 100%.
- Kept exact counts in summary tiles and on each bar tooltip, including per-day denominator/unavailable counts. Historic values remain point-in-time from the immutable radar archive; no changes to stage thresholds, membership, Telegram sends or data schema.
- Affected: `lab/app.js`, `lab/trend-birth-quality.js`, `lab/styles.css`, `lab/index.html`, `tests/trend-birth-quality.test.cjs`.
- Verification: regression tests added for unequal daily denominators, 0% and 100%, and fixed-axis markup; GitHub CI should run before production merge.
- Caveat: on a genuine 0–100% scale, small 3/4+4/4 percentages produce short bars; numerical percentages and exact counts remain available to avoid misreading the magnitude.

## 2026-10-24 — Trend Birth 0/4–4/4 setup breadth and dated chart

- Topic branch: codex/trend-birth-quality-history-20261024, based on the production app branch feature/unified-review-grid-lab. Production publication requires review/CI and merge.
- Dashboard: five exact daily counts, evaluated/unavailable denominators, a 3/4+4/4 breadth percentage and selectable history chart. Archived links cannot see future observations.
- Existing verified radar is sole source. A compact index is reconstructed from immutable daily archives; pre-radar dates are omitted, not zero-filled. Counts reconcile and use a common universe scope.
- The legacy no-send EOD Telegram alert text includes the same distribution and verified link; separate Unified hourly counts are clearly labeled as narrower intraday Kell/watchlist scope.
- Affected: app HTML, JS and styles; quality history builder; publisher; no-send alert formatter; tests and docs. No scanner membership, thresholds, ranking, broker path, or sender infrastructure changed.
- Verification: 134 Python and 58 Node tests passed before execution environment reset; reconstructed GitHub commit requires PR CI.
- Limits: selected-universe breadth, not all-listed-stock breadth or a forward-return backtest. Denominator changes as selected universe varies.

## 2026-10-21 — Installable Trend Birth mobile app

- Branch: `codex/trendbirth-mobile-pwa`, based on production app commit `7a8e7caf91515eb2a6af2fc572e0788552d17801` on `feature/unified-review-grid-lab`. Implementation SHA is the commit containing this entry; activation will be recorded after deployment verification.
- Added a standalone PWA manifest with a stable root identity/start URL, original Trend Birth SVG/192px/512px/maskable/Apple icons, Android install prompt and browser-menu guidance, iPhone Safari instructions, and an install dialog. Archived links retain their exact URL; installing from an archive starts future home-icon launches on the current review.
- Reflowed the mobile topbar into full-width branding and two columns of controls, increased touch targets, prevented input-focus zoom and added safe-area padding. Existing cards, sorting, chart periods, filters and watchlist behavior are retained.
- The worker caches only install artwork, manifest and an explicit offline screen. Market snapshots, current publication pointers, chart data, account requests and app/auth scripts always use the network. Open pages show an offline warning; cold offline launches show retry guidance. Updates wait for a user-triggered refresh that preserves snapshot parameters. Offline fallback normalizes redirected hosting responses for Vercel clean URLs.
- Reuse audit: EXTEND Unified's standalone-manifest concept with a separate app identity and install UI; REPLACE market/snapshot caching with an explicit offline screen for this lab. Reviewed preferred Next source documentation and confirmed its current main lacks `frontend/public/sw.js`; no engine code imported and no other repositories modified.
- Affected: `lab/index.html`, `lab/pwa.css`, `lab/pwa.js`, `lab/sw.js`, `lab/offline.html`, `lab/manifest.webmanifest`, `lab/icons/*`, `lab/vercel.json`, mobile documentation and `tests/pwa.test.cjs`.
- Validation: 129 Python tests and 53 Node tests passed; JS syntax and diff-whitespace checks passed. Chromium used the actual 2026-10-20 publication (`2026-10-20-eod-39518546268-1`): 15 Weekly Birth cards rendered, chart detail opened, local watchlist survived reload, invalid snapshot failed visibly, exact archive survived offline/retry and a worker update. Layout had no horizontal page overflow at 320/360/393/430/1024/1440px; Android/manual install and iPhone instructions were exercised. Persistent Chromium reported no installability errors. Native OS installation and an actual iOS browser were not available; the native install event was simulated and manual guidance verified. No account sign-in or external notification was performed.
- Impact: presentation/installation only; candidate membership, ranking/scoring, weekly/Kell definitions, publication data, owner auth/sync and Unified pipelines unchanged. Internet remains required for review data. Cross-browser local watchlists are not migrated by installation.
- Next: verify branch CI and the deployed HTTPS manifest/worker/offline behavior, then record exact accepted implementation/deployment identity and installation URL.

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


## 2026-09-24 — Kell Trend Birth 0/4–4/4 radar

- Branch: `feature/kell-trend-birth-radar`, based on `feature/unified-review-grid-lab`. StockScout Unified candidate generation, rankings, production Telegram sender and broker behavior were not modified.
- Added a transparent Trend Birth lifecycle overlay for the existing Unified/Kell candidate universe:
  - **0/4** NO SETUP / INVALIDATED
  - **1/4** WATCH: rising SMA50 + true rising SMA30W + valid/non-extended structure
  - **2/4** WATCH CLOSELY: current price near SMA50 in ATR units + EMA10/20 compression
  - **3/4** READY: short EMAs flatten/turn, with at least one positive normalized slope
  - **4/4** TRIGGER: recent pullback/compression, EMA10 rising, EMA20 non-falling, EMA10 > EMA20, close above both and bullish re-expansion/fresh cross.
- ATR14 uses Wilder/RMA. Price-location and compression thresholds are ATR-normalized; no fixed dollar price zone is used.
- Decorated full `unifiedCandidateIndex`, Kell candidates and Review candidates with a `trendBirth` evidence object containing stage, every boolean check, key metrics and `missingFor4`.
- Compact Kell data now preserves the radar and top-level stage counts. GridView adds TB 2/4, 3/4 and 4/4 filters, TB Ready / TB Trigger quick views, stage badges and the full ✅/❌ checklist in ticker detail.
- Added `scripts/build_trend_birth_alerts.py` as a **no-send** alert exporter. It preserves the architecture boundary that Trend Birth owns data while Unified remains the Telegram sender.
- Anti-noise alert contract: no 1/4 alert; no individual 2/4 alert; new 3/4 names are grouped and capped to top 5; every new 4/4 is represented; invalidation is emitted only for names previously at 3/4 or 4/4. When candidates are omitted, the exact `+N additional candidates — View dashboard: <URL>` link is always included.
- First production day is baseline-only if the previous Kell archive has no `trendBirth` evidence, preventing a mass Telegram flood on rollout.
- CI run **#305** / run id **36058522852** completed green end-to-end: Python tests, historical Kell smoke, browser tests, JavaScript syntax, live Unified snapshot rebuild, compact Kell + chart shards, no-send alert payload, source-identity validation, Kell signal validation, Gold Set, forward validator and artifact upload all passed.
- Live validation session remained `2026-09-23`: 2,672 Unified candidates, 2,004 Kell matches, 2,004 chart-covered Kell candidates; Trend Birth compact validation passed across every Unified candidate entry.
- The isolated branch deliberately skipped aligned-data publication; no production dataset or Telegram notification was changed by the validation run.

**Next logical step**
- Merge the tested radar into `feature/unified-review-grid-lab`, let the existing refresh/deploy chain publish it, then teach the existing Unified GridView Telegram sender to consume the verified no-send alert payload without changing candidate generation or creating a second Telegram owner.


## 2026-09-26 — GitHub-native review agents

- Branch: `chore/github-review-agents`, based on `feature/unified-review-grid-lab`; no production Unified EOD / Telegram / broker behavior changed.
- Added repository-wide Copilot code-review instructions in `.github/copilot-instructions.md`.
- Added three read-only GitHub Copilot custom agents:
  - `stock-selection-reviewer` — detects hidden changes to candidate membership, ranking, scoring, Trend Birth/Kell semantics, filters and evidence provenance.
  - `regression-reviewer` — checks CI, snapshot/source identity, compact/shard contracts, watchlist behavior, fallback paths, UI regressions and production isolation.
  - `merge-gate-reviewer` — final P0/P1/P2 gate that can delegate independent methodology and regression passes before reconciling findings.
- Agents intentionally omit edit/write tools and are instructed never to push, merge, close, approve or mutate repository state.
- Review standard requires explicit BEFORE/AFTER semantics for methodology-sensitive PRs and treats descriptive evidence becoming a hidden gate/rank/weight as a review defect.
- Copilot review instructions require high-signal P0/P1/P2 findings, distinguish behavioral tests from source-shape assertions, and preserve the Unified -> Review -> Kell architecture boundary.
- This is review infrastructure only; candidate generation, detector thresholds, Trend Birth 0–4, Kell scoring/ranking, alerts and production data are unchanged.

**Next logical step**
- Validate the agents from GitHub Copilot Agents on this branch and, after merge, enable/use repository custom instructions for Copilot code review. Automatic Copilot review assignment remains a repository setting rather than a file-level behavior.


## 2026-09-26 — Trend Birth supporting-evidence ranking neutralized

- PR: #31; merged into `feature/unified-review-grid-lab` as `1cbeff6428b8bd962672ccf697aa12b3c8dd135a`.
- A post-merge audit of the Recovery -> Compression -> Ignition supporting-evidence layer from #30 found that `pathRank` and `birthEvidenceCount` had become hidden inputs to the explicit `trend-birth` sort.
- BEFORE: within Trend Birth stage, ordering included Birth Path phase (Ignition > Compression > Recovery), then evidence count, then Kell score.
- AFTER: Trend Birth ordering is restored to Trend Birth stage first, then the existing Kell score. Supporting evidence remains available as explicit Recovery / Compression / Ignition filters, badges and detail text.
- Affected files: `lab/app.js` and `tests/filter-hierarchy.test.cjs`.
- Candidate generation, detector thresholds, Trend Birth 0-4 stage logic, Kell score calculation, Unified EOD, production Telegram and broker behavior are unchanged.
- Regression coverage prevents `pathRank` / evidence-count terms from re-entering the Trend Birth sort expression. This guard is source-shape based; a synthetic same-stage behavioral ordering test would provide stronger future protection but was not required for this narrow repair.
- Validation: Unified Review Grid Lab run #349 passed end-to-end on the PR head; Vercel preview was Ready; manual review found no P0/P1/P2; the GitHub-native `merge-gate-reviewer` ran in GitHub Actions run `36246518896` and returned `MERGE GATE: CLEAN` with no final P0/P1/P2 findings.
- Post-merge verification on `feature/unified-review-grid-lab` confirmed the active sort is `trendBirthStage(item) * 1000 + Number(item.kell_score || 0)` and all three GitHub review-agent profiles remain present.

**Next logical step**
- Keep Recovery / Compression / Ignition as explicit supporting evidence rather than an implicit ranking prior. Add a behavioral same-stage sort regression only when the UI sorting harness is next touched or if an equivalent ranking leak recurs.

## 2026-09-26 — Weekly Birth v2 shadow implementation

- Branch: `codex/weekly-birth-v2`, based on `feature/unified-review-grid-lab`.
- Added a weekly base, MA compression, resistance runway, extension and fresh-breakout evaluation over completed weekly bars. Each candidate carries checks, measurements and rejection reasons; the shortlist is capped at 15 without filling weak slots.
- Snapshot and compact Kell payloads now carry separate `weeklyTrendBirth` and `kellDaily` shortlists while retaining the existing fields and legacy alert contract. The GridView exposes Weekly Birth, Kell Daily and Research Universe, with a five-year weekly chart as the new default and a `legacy` switch.
- Added grouped no-send weekly/Kell alert payloads and an initial baseline-only v2 session. PR validation is read-only; the feature branch workflow publishes aligned data and then runs historical Gold Set/forward calibration in a separate artifact-producing job. The Kell spot-check now selects references only when present.
- Added a GitHub-native watchdog, a per-session no-send shadow audit with counts/reasons/membership changes, and a rollout/rollback runbook. The watchdog must land on the repository default branch to become active.
- Release gate: five market sessions in shadow mode and at least 25 manually reviewed weekly charts remain pending. No v2 Telegram mode is enabled by this code change.

## 2026-10-24 — Grouped EOD digest and point-in-time setup stability (implementation)

- **Branch/PR:** narrow topic branch based on `feature/unified-review-grid-lab`; fill final PR/commit/deploy SHA after CI and production verification. Existing repo `StockScout-Unified` already merged sender compatibility PR #112.
- **Motivation:** EOD payload previously contained potentially dozens of independent `trigger` Telegram messages (plus `ready`, `invalidated` and `intelligence-eod`). Today displayed transitions but not whether 4/4 held multiple actual sessions.
- **Changes:** group all narrow Review EOD changes in one authenticated-source `intelligence-eod` digest when a matching intelligence JSON is present. Keep full message counts `readyCount`, `triggerCount`, `invalidatedCount`; show capped named lists with correct overflow and stable dashboard URL; preserve legacy fallback without intelligence and untouched hourly/weekly-v2 senders. Derive durability from existing permanent per-ticker monthly archives (no new job, backend, DB, provider, or data-retention change) and expose quality ≥3 and exact 4/4 streaks, historical paired-session retention with denominator and latest dropouts.
- **Precise definitions:** `qualityStreak` = consecutive *observed archived EOD sessions* where stage≥3, `fourStreak` = stage exactly 4; absence or unavailable breaks continuity, never 0/4. Retention denominator counts qualifying tickers on prior session only when evaluable in next archived session; numerator counts those still in the same category next session; dropouts count only comparable names in final pair. No use of future observations as of latest date; no claim that signal persistence forecasts returns. Current `topOpportunities` carries per-ticker streak, no change to Kell sorting, ranking, stage definitions, or selection.
- **Data cross-check** from published September + October 2026 monthly files (20 sessions to 23 Oct): 3+/4 current=163, streak≥3=69, ≥5=28, next-observed-EOD retention=2494/3576=69.7%, latest dropouts=38; exact 4/4 current=105, streak≥3=21, ≥5=3, retention=1177/2069=56.9%, latest dropouts=39. Latest `trend-birth-intelligence.json` enriched after reconciling `runId`, date, counts with newest retained point.
- **Files:** `scripts/trend_birth_intelligence.py`, `scripts/build_trend_birth_alerts.py`, `lab/index.html`, `lab/app.js`, `lab/styles.css`, `lab/trend-birth-intelligence.js`, updated compact `lab/data/trend-birth-intelligence.json`, Python/Node targeted tests, `HANDOFF.md`, this log.
- **Verified 24 Oct (Europe/Zagreb):** PR #52 merged with production commit `e1c83658d62a0bc78b7c71f3fe65ff2c3bd29d8f`; GitHub CI run `40123181558` **success** across Python/Node, model/browser behavior and snapshot publication checks. Independently ran 21 Python tests in a read-only runtime (the one filesystem-temp test was covered by CI) and 8 Node tests. Vercel production deployment `dpl_3pgnTFURvWN29TVpiSyVwA9hoHSo` **READY**; observed live DOM: 69 quality≥3-streak, 21 exact-4-streak, 38/39 latest dropouts and paired retention 69.7%/56.9%; TRGP quality streak 12 and exact 4 streak 1. Existing sender `StockScout-Unified` accepts the `intelligence-eod` kind, confirmed from its live `main` source. The historical 23 Oct alert payload remains immutable with 65 messages (62 individual triggers); the future new EOD generated payload will group them to one intelligence message. **Actual Telegram delivery awaits the next scheduled EOD; never claim sent until ledger verified.**
- **Next:** verify first new scheduled EOD and grouped Telegram sender ledger, then consider forward return analysis with much longer point-in-time history and independent controls before changing setup quality thresholds.


## 2026-10-24 — Market Internals v1 / zaseban tab Statistika (topic branch)

- **Referentna aktivna grana:** feature/unified-review-grid-lab; GitHub HEAD provjeren na 3db166a1301d7ba6186f71874cc54769bfe2d825 nakon automatske EOD publikacije. Topic: feature/tb-market-internals-20261024. Status prije mergea: priprema i lokalna sintaksa/sintetička kontrola, CI/deployment još se provjeravaju.
- **Zašto:** korisnik traži posebno izdvojen statistički tab, dugotrajnu povijest cijelog skupa setupa, mjeru smjera i akceleracije, migraciju stage 0→4 i statistički percentil, bez plaćenih Vercel/GitHub resursa.
- **Podatkovni model:** sve stvarno sačuvane EOD sesije s punim ticker-stage arhivama ulaze u kompaktnu seriju. Nema ograničenja 20 dana, nema fiktivnih ranijih točaka. Dodan točan 5×5 model prijelaza samo za tickere evaluirane na oba kraja EOD para; coverage/intersection/unavailable ne mapira u 0.
- **Metodologija:** Breadth3+=100(N3+N4)/N, Breadth4=100N4/N, Pressure=100Σ(sNs)/(4N). Velocity je OLS pp/EOD zadnjih N sesija, acceleration razlika istog OLS nagiba između tekućeg i prethodnog nepoklopljenog N-EOD prozora, null ako nema 2N podataka. W/M = ponderirano zbrojem ticker-dana; percentil je point-in-time rang u odnosu na prethodne dnevne sesije istog pokazatelja uz n; transitions su upareni prema istom tickeru.
- **Podaci (24.10., zadnji zabilježeni 23.10. EOD):** 20 EOD, 11.2 KB kompaktne serije; 2614 validnih tickera, 2222/182/47/58/105 u fazama 0/1/2/3/4; 3+/4=6.2357%; Pressure 8.3206/100; 2602 zajedničkih tickera, +61 ulaza i −38 izlaza, net +23; nikad ne tvrditi da je to cijelo tržište.
- **Datoteke:** novi lab/statistics.html, lab/trend-birth-stats.js, lab/trend-birth-stats.css, lab/data/trend-birth-market-internals.json, docs/MARKET_INTERNALS_ROADMAP.md; izmjene lab/index.html, lab/styles.css, scripts/trend_birth_intelligence.py, .github/workflows/unified-review-grid-lab.yml, tests/test_trend_birth_market_internals.py, tests/trend-birth-market-internals.test.cjs, docs/ROADMAP.md, HANDOFF.md i ovaj log.
- **Resursi:** bez novog API-ja, data storea, workflowa ili rasporeda. Postojeći EOD izračun radi iz već sačuvanih mjesečnih sharda; Vercel statički build kopira HTML/CSS/JS, mali JSON služi postojeći /data/* GitHub Raw rewrite.
- **Testovi prije PR-a:** Python compile izvršen, sintetički tokovi/coverage i JS validacija stvarne 20-EOD serije prolaze; puni GitHub CI i produkcijska vizualna provjera odvojeni su sljedeći korak. **Ranking, trigger uvjeti i Telegram slanje nisu izmijenjeni.**
- **Sljedeće:** otvoriti PR, provjeriti CI i live tab, paziti na mobilni izgled i iduće EOD osvježavanje; nakon toga Faza 2 cohort survival i uvjetne stopa izlaska prema roadmapu.


### 2026-10-24 — Verified PR #53 merge, production deployment and UI

- PR #53 successfully merged via squash to active `feature/unified-review-grid-lab` as `1eb8ebe55435d33241cee5914968a73e07bc7905`; GitHub CI run `40127378812` completed **success** (model/browser regression, Python and Node tests, snapshot publication pipeline).
- Vercel production `dpl_YYrCvvQChjC8DkENgRGbNsngGo9m` reached **READY**; live Chrome browser loaded production /statistics, displayed 20 EOD values, 6.24% quality breadth, pressure 8.32, velocity 0.05 pp/EOD, acceleration 0.34 pp/EOD, 36.84 percentile on n19, matched net flow +23; 19 EOD transition pairs and 49,971 matching ticker transitions. Preview manually switched metric to acceleration and D to M; chart rendered with symmetric signed axis, missing values left blank when history insufficient. Screenshot visual QA passed.
- No change to ranking, risk, Telegram sending or scanner cadence; no additional Vercel storage, cron, or external data. User sees independent Statistika tab; 11KB compact data remains served through existing GitHub Raw rewrite.
- **Pending:** verify next *new* scheduled EOD refresh updates internals + intelligence + snapshot on the same runId/date and retains all historical points, and verify next grouped Telegram alert delivery in ledger.


## 2026-10-24 — Walk-forward Composite Score / 14 ETF proxy (eksperimentalno)

- Novi `scripts/backtest_market_internals.py`, `tests/test_trend_birth_composite.py`, te `lab/data/trend-birth-composite-backtest.json`. Pinani izvor je `manisahni/marketdata` commit `65a079329e379e104495f459e12e76a8f995585a` (dividend-adjusted closes od 2004., 14 equity ETF-ova, 9 sektorskih + QQQ/IWM/EFA/EEM/VNQ); bez pohrane velike CSV kopije. Iz izvora se uklanjaju iskljucivo redci bez svih equity cijena (primjer 2026-05-25 i prazni kraj 2026-08-11), a broj takvih redaka cuva se u JSON-u.
- Backtest: walk-forward godisnji, H20 SPY total-return proxy, sljedeci adjusted CLOSE kao ulaz, 10-session stride, 11 predeklariranih modelskih profila, 2008–2026 OOS, obavezni kriza/rast/režim VIX izvjestaji; **nije replay stvarnih povijesnih StockScout setupa**.
- Sest komponenti s historijskim percentilima na vlastitom izvoru; aktualni Composite iz stvarne EOD arhive 2026-09-24 nadalje. Profil ETF proxy prenesen je indikativno, bez dokazane stock-level prediktivnosti.
- Tab `lab/statistics.html` prikazuje score 0–100, sve periode pozitivne/negativne validacije i metodoloske napomene. GitHub workflow lokalno osvjezava aktualni score bez dodatnog network backtesta ili crona.
- Inkrementalni EOD graf `lab/data/trend-birth-market-internals.json` ostaje samo stvarni feed (D/W/M, 1M/3M/1Y/5Y/All), nikakve sinteticke sesije.
- **Sljedece:** kvaliteta cijena/OHLC i dinamicni universe/delistings, neovisni kalibracijski i finalni holdout, provjera metodoloskog rizika te nakon 120+ stvarnih EOD sesija validirati score na punom StockScout univerzumu. Negativni rezimi ukljuceni su u izvjestaj.


## 2026-10-25 — Stvarni ishodi ulaska u Trend Birth faze (5/20/60 EOD)

- Implementacija: `scripts/trend_birth_stage_forward.py`, `tests/test_trend_birth_stage_forward.py`, kompaktne mjesečne arhive `lab/data/trend-birth-forward-history/YYYY-MM.json` te sažetak `lab/data/trend-birth-stage-forward.json`. Jedini ulaz su **već arhivirane** point-in-time ticker faze i `trendBirthCandidateIndex.chartBars` iz postojećeg `latest.json`, bez novih skenova, servisa ili rasporeda.
- Event definicija: isti ticker mora biti valjano evaluiran u dvije uzastopne zabilježene EOD sesije te promijeniti fazu 0–4. Prvi zapis tickera nikad nije automatski ulazak. Jedan event po tickeru/prijelazu; isti ticker može imati više vremenski razdvojenih događaja, koji nisu statistički neovisni.
- Cijene: signal poznat na EOD zatvaranju; **ulaz na idućem AAPL-burzovnom zatvaranju**, potom izlaz za 5, 20 ili 60 cijelih burzovnih sesija. Koristi close-to-close promjenu bez dividendi, slippagea i troškova; rezultat je promatranje, ne izvršen nalog. Nedospjeli eventi ostaju pending; dospjeli bez oba closea broje se u missing, nisu nule. Calendar/price freshness fail-closed.
- Svaki dovršen outcome ostaje u malom mjesečnom shardu i kad 260D chart prozor kasnije istekne. Ranije arhivirane faze se ne prepisuju; konflikt događaja/runId za isti dan izaziva fail. Sažetak: za svaku fazu × horizont broj, prosjek, medijan, win-rate, P10/P90, očekivana/dobivena pokrivenost, pending i missing. Prikaz u `lab/statistics.html` zasebno od **ETF proxy Composite**.
- CI workflow: postojeći dnevni job izvršava skriptu nakon arhiviranja faza, čuva i objavljuje mjesečne sharde + sićušan JSON; bez nove Action minute iz zasebnog joba i bez novih Vercel funkcija. Testovi: čista Python sintaksa+core, Node sintaksa, CI unittests.
- **Važna ograničenja:** nedostupne/delistane dionice mogu imati missing outcome (coverage guard); cijene su iz Unified charts i mogu imati split-ali nisu nužno dividend-adjusted; višestruki prijelazi istog tickera i preklapanje 5/20/60 ishoda → nisu nezavisne oklade. `eligibleForCalibration` tek ako pojedina kombinacija faza/horizont ima >=250 dospjelih opažanja, >=20 različitih signalnih dana i >=99% pokrivenosti, ali **ni tada nije automatska promjena Composite težina** bez neovisnog holdouta.
- **Dalje:** provjeriti da CI/GitHub publication i Vercel `statistics.html` u produkciji daju report nakon sljedećeg EOD; dodati benchmark-relative SPY (ako stabilan izvor), survivorship/delisting review, klasterirane intervale pouzdanosti i odvojeni kalibracijski vs budući holdout na većem uzorku.

---


## 2026-10-25 — Real EOD workflow postmortem and calendar hotfix

- GitHub Actions run #400: new 5/20/60 script failed after passing all Python/Node tests because rotating candidate union omitted AAPL; full publication correctly stopped. Fixed by strict-majority (>50%) date quorum across all valid CURRENT Unified chart bars, preserving fail-closed behavior if no coherent market calendar. Regression test added for absent AAPL. Verify follow-up publication and data output before claiming live outcomes.


## 2026-10-25 — Native chart normalization correction

- Additional inspection of `scripts/build_review_snapshot.py::_chart_rows` and `_date_from_stamp` confirmed Unified chart rows may be compact arrays and timestamps in seconds/milliseconds; stage-forward `_bars` originally accepted only dict bars. Implemented both formats with UTC time normalization and a contract test, alongside majority-calendar fallback. This is necessary for live end-to-end EOD success.


## 2026-10-25 — Stage forward V2: actual full-universe EOD close archive

- **Why:** production run #402 completed and published stage-forward V1, but **5D outcome coverage was only 43 / 4,368 matured stage entries (about 0.98%)**. The historical prices inside today's rolling Unified chart bars failed to align for most tickers; those averages are not representative and must not calibrate Composite.
- **V2:** use immutable EOD Review snapshots to extract exactly one `metrics.price` per *evaluated ticker per actual day*, preserving `runId` and session-date identity. New script `scripts/archive_trend_birth_closes.py` backfills only missing historical sessions once from existing `lab/data/history`, then processes the new EOD daily. Compact monthly `lab/data/trend-birth-price-history/YYYY-MM.json` keeps every date permanently, without new APIs/services/scans.
- Compute next-EOD-close entry +5/20/60 fully elapsed **exchange-session** closes from the price archives, not from the rolling charts (those now supply **dates only**). New immutable `lab/data/trend-birth-forward-eod-history/YYYY-MM.json` uses schema V2, so 43 prior V1 chart-only results remain available for audit in legacy `trend-birth-forward-history` but cannot contaminate V2 samples. Report `lab/data/trend-birth-stage-forward.json` now schema V2, UI validator updated.
- New snapshot price-contract unit tests; existing stage-entry, chart calendar, pending/missing, immutable archive tests updated. Workflow: price extraction and stage forward after existing stage archive, both monthly archives and compact report included in existing atomic publication. App stays static on GitHub/Vercel.
- **Guardrails:** `metrics.price` is the recorded EOD source quote, not necessarily dividend/split-adjusted; percentages remain descriptive only. Incomplete source-session snapshots are not filled, and missing EOD dates do not become artificial trading sessions. When stock splits/delistings occur, later add corporate-action checks and delisted-outcome review before statistical weight calibration.
- **Next:** inspect real 5D n/coverage from new GH Actions publication. Hold Composite ETF proxy weights unchanged; after 20D/60D maturity and robust sample, use chronological holdout with controls before recalibration.

---


## 2026-10-25 — Stage-forward V2: forensic EOD coverage audit

- **Branch:** `feature/tb-forward-coverage-audit-20261025` based on `feature/unified-review-grid-lab` after PR #59; commits visible in corresponding PR history.
- **Problem and evidence:** run #403 and V2 report (2026-10-23) show 20 archived EOD snapshots with 100% quote coverage for the evaluated universe, versus 22 dates on the latest majority-chart exchange calendar. Whole-market price snapshots missing for 2026-10-15 and 2026-10-19; 5D outcomes have 71.55–78.38% mature coverage, so means are selection-biased and cannot support score calibration.
- **Change:** `scripts/trend_birth_stage_forward.py` now audits every missing matured ticker-stage outcome as missing whole session, missing ticker quote on otherwise archived sessions, or unclassified (e.g. older calendar no longer retained), and verifies exact reconciliation. Source-session coverage, missing dates and quote coverage join the compact V2 report. `lab/trend-birth-stats.js` and `lab/statistics.html` surface these facts beside the 5/20/60D table with fail-closed consistency checks. No historical prices or stage outcomes are imputed or overwritten; 99% future coverage is insufficient for calibration while complete EOD sessions remain missing.
- **Safety / tests:** `scripts/trend_birth_stage_forward.py` also rejects `runId` / evaluated-count mismatch between stage and price archives for each date. Regression cases in `tests/test_trend_birth_stage_forward.py` and `tests/trend-birth-market-internals.test.cjs` cover missing exchange-day attribution, ticker-only gaps, provenance mismatch and invalid aggregate counts. CI and production verification pending at the time of recording.
- **Method caveats:** dates are inferred from the current majority chart calendar; missing historical dates cannot be fabricated. Price source remains unadjusted for dividends/corporate actions, exits can be delisted, and repeated ticker events are dependent. ETF proxy Composite weights and production ranking remain unchanged.
- **Next:** PR checks, branch merge, Vercel live data audit; consider verified missing-session recovery from preserved historical EOD sources, split/delisting handling, and chronological test-vs-holdout before any outcome-based weighting.


## 2026-10-25 — EOD source-artifact preservation before expiry (P1)

- **Verified production predecessor:** PR #60 merged `d842be64`, Vercel deployment `dpl_FEuP4b7hyKvRYrV7PgpsEv1R2Swz` READY. GitHub Actions run 40147700778 `build` success; published stage-forward V2 compact JSON reports 20 archived of 22 exchange sessions and both Oct 15/19 gaps; all 52,951 expected EOD quotes present for existing dates. No statistical recalibration.
- **Exact source IDs:** Unified Pages 2026-10-15 artifact `12016667723` (run `38825335004`, SHA256 `b8595b0e05da8d41cf8523b94b5d799a7e911efa697206cf84c97ed4e4f25e7a`, Oct30 expiry); 2026-10-19 artifact `12235521722` (run `39347937228`, SHA256 `5e7041b976d902d12f6f5e84d84591d230ed9ee9e10df805e198cca41c9cf103`, Nov3 expiry). Both ZIPs downloaded from GitHub before expiry; temporary download alone is not long-term preservation.
- **Topic branch:** `feature/tb-eod-artifact-preservation-20261025` implements `scripts/preserve_unified_eod_evidence.py` and `tests/test_preserve_unified_eod_evidence.py` with one-shot `.github/workflows/preserve-unified-eod-evidence.yml`. It validates upstream workflow-run metadata, exact ZIP size/SHA256/CRC, inner Pages date/run identity across four manifests and draft release asset integrity before declaring success. ZIPs and sidecar manifest are kept as a draft Release, not Git blobs, avoiding another ~322 MB of Git history and Vercel clone payload. Release job pending verification at time of log entry.
- **Data-contract safety:** no change to immutable stage, price or outcomes; no invented EOD prices, no recomputation or ranking/Telegram change. Inserting intermediate dates retroactively could change entire event sequence, so require separate versioned reconstruction with before/after event diffs, full source provenance and reversible migration proposal before publishing corrected history.
- **Follow-up:** verify one-shot workflow and retained evidence assets; inspect original saved Pages manifests for source identity and point-in-time ticker universe, then design safe V3 side-by-side archive, corporate-action/delisting audit, SPY-relative controls and chronological holdout before Composite recalibration.


## 2026-10-25 — Source evidence now safely retained; checkout footprint investigated

- **Durable evidence:** GitHub Release API independently confirmed complete **draft** source-evidence releases in Trend Birth (`423075292`) and Unified (`423075968`). Both each hold original Oct15 and Oct19 ZIPs with byte sizes 162,020,086 / 159,822,532 and SHA256 checksums exactly equal to expired-soon source Actions artifact metadata; each includes a small provenance manifest. No binary blobs added to Git history. GH Actions `40148655786` completed all unit tests, downloaded, SHA/CRC/inner manifest verified and uploaded all three release assets; its last step failed only because GitHub draft release is absent from `/releases/tags/...` endpoint; fixed to query authenticated `/releases?per_page=100` and verify assets. PR #63 follow-up tests and re-verification queued at this checkpoint.
- **Main publication:** GH Actions production run `40147700778` `build` success and stage-forward V2 JSON now has `dataQuality` with 20/22 sessions, Oct15/19 missing, 52,951 actual vs expected quotes. Static Statistika UI deployment READY; weights unchanged.
- **Tree footprint:** read-only recursive GitHub tree `ed9588cc46300007b5b3a543ccaa9b6d24a5529d` (1,332 files) shows 9,452.5 MiB in checked-out content: `lab/data/snapshots` 4,964.2 MiB, `history` 1,937.3 MiB, `kell-chart-runs` 1,080.4 MiB, `kell-snapshots` 839.5 MiB, `kell-history` 392.2 MiB. The lightweight `lab/build-vercel.mjs` excludes these datasets from deployment output. Do not perform destructive cleanup until #64's complete archive/restore/backtest checks; archive source bytes and measure before/after clone time. A sparse checkout for the one-shot evidence workflow was added to limit this job to its two scripts/tests rather than 9.23 GiB of lab files.
- **Boundary:** neither original source retention nor storage audit inserts missing dates into immutable stage/outcome histories. Versioned V3 replay requires historical tracked-watchlist membership and exact source chart/scanner identity; no ranking, Telegram, Composite or production EOD model changes.

## 2026-10-25 — Historical Composite Score chart with six-factor audit (new topic branch)

- **Context/source:** Existing `trend-birth-composite-backtest-v1` = 466 10-session-spaced ETF-proxy OOS observations, 2008–2026; original source SHA256 `361efb287116fc8200582c15fcd315bcce2e218fa1e50b416bacc5acebff37b9`. Live `trend-birth-market-internals` = 20 genuine EOD scans ending 2026-10-23, with important incomplete factor lookbacks. The selected `recovery` profile weights `[2,2,3,3,3,1]`, directions `[-1,-1,1,1,1,1]`, last actual score 69.6617, original +0.883 pp ETF OOS spread (research-only).
- **Change:** Preserve the same score algorithm and annual historical model-selection logic. Export complete chronological OOS observation traces and recalculated actual EOD history into the existing compact JSON; historical OOS fields include the source-date score, year-selected profile, prior-only rank/raw inputs and label-end plus *retrospective* SPY H20 return, never used as features. Real observations show eligible prior-history counts per factor; neutral 50 fallback from `percent_rank` is visibly flagged for shorter than 12 prior points or absent feature.
- **UI:** New line chart in `lab/statistics.html` with real-vs-proxy source switch, 1M/3M/1Y/5Y/All range, selectable observation via slider or tap, and audit table: raw factor, percentile, normal/inverse sign, weight, contribution and reliability. Yearwise changed profiles are disclosed for ETF OOS. Relative slope/acceleration and actual prior 20-day breadth are not rewritten; no manufactured missing sessions. Warn that the current score is an indicative fixed ETF-weight transfer rather than stock-level OOS.
- **Cost:** One branch-only, non-recurring, sparse-checkout job downloads the same pinned public ETF CSV, regenerates small score JSON and runs specific Python/JS assertions; no new paid provider, no additional EOD scan, no raw archive copy, no changes to large immutable records. Production-only build and standard PR checks still required.
- **Regression:** Require unchanged source SHA, 466 test samples, 2008–2026 OOS range, +0.883 pp historical spread, 14-weight recovery formula, reproducible actual score. Python tests prevent future leakage; Node tests check timeline data integrity, equation parity and warm-up visibility. Keep StockScout live rankings and alerts entirely untouched.
- **Stage:** Implementation prepared in topic branch; at this checkpoint actual one-shot and full PR CI/deployment verification still pending, so do not advertise as already live.

## 2026-10-25 — Statistics review corrections: publication, mobile, calendar and evidence

- **Branch/commit:** `fix/statistika-review-20261025`, implementation `12af4569385243607b44b6306237c6f33286a5ec`, base `67335b953cef64ba57bbf3ae4f8e03f9db4dedbf`. Local validation timestamp: 25.10.2026. 12:50 Europe/Zagreb (11:50 UTC). PR CI/review and production rollout are pending.
- **Problem/behavior:** the publication step discarded the newly refreshed tracked Composite file during `git reset --hard`. Preserve it with the existing temporary bundle and assert the final Composite date/score and internals identity before commit. A behavioral test executes the actual shell against a temporary local Git remote; it covers a successful new session and a stale score that must block publication.
- **UI:** reveal the selected heat/Composite marker inside its chart's horizontal scroll area, including on a 390px phone. Keep document scroll unchanged; recover source/date synchronization when forward/calendar loading finishes late. The HTML script versions are refreshed.
- **Calendar/data contract:** stage-forward now exports its already computed exchange-session dates as optional `exchangeSessions`; no outcome values or immutable event shards change. Heat continuity uses those actual dates, with a compatibility path from an aligned old V2 coverage report's observed dates plus explicit gaps. Unknown calendar coverage does not establish continuity or trigger a fabricated missing-session warning. Tests cover Thanksgiving, Good Friday, a Monday holiday, actual absent EODs and unavailable/stale calendars.
- **Integrity:** numeric input validation rejects missing/null/string/non-finite percentages and inconsistent paired overlap/flow. Release reuse validates the complete manifest against both pinned `SOURCES`, then checks original ZIP assets; empty, incomplete, duplicated or replaced source sets fail before remote lookup. The real existing draft evidence release passed stricter read-only verification.
- **Affected:** two existing workflows; Statistics HTML/JS; `preserve_unified_eod_evidence.py`; `trend_birth_stage_forward.py`; focused Python/Node/Chromium regressions; `lab/README.md` and `HANDOFF.md`. Chromium is pinned to Playwright 1.62.1 in PR validation only; the scheduled EOD job gains no browser install, extra scan or extra job.
- **Methodology:** before/after equality verified for all fields of the 20 existing computed heat records, not just the final score. Composite formula/weights, ticker ranking/stages, provider inputs, existing JSON archives and Telegram behavior remain unchanged. Calibration still requires separate methodology work; this patch does not repair missing historical sessions or corporate-action handling.
- **Validation:** 188/188 Python, 98/98 Node and 4/4 Chromium browser tests; static build; both workflow YAML parses and shell syntax; clean `git diff --check`. Browser cases include visible mobile markers, synchronized date/range, independent ETF source, delayed calendar response and safe unavailable-calendar behavior. Remote CI and preview still require verification after pushing the PR.
- **Next:** inspect the fix PR's CI/preview, merge after review, then verify Composite and internals agree on the next real EOD. Preserve V2 archives for a separate versioned missing-session recovery and split/delisting audit.



## 2026-10-26 — Application review: bounded startup and correctness fixes

- **Checkpoint:** 2026-10-26 13:39 UTC; topic `fix/trendbirth-review-20261026`, baseline `168fc51bfc207e134d29e6b30201e7c087c3c1d8`. Production baseline independently rechecked in Vercel as `dpl_9D9QbegVHSDyQPiPoaoJf1k6DsiV` READY; topic is not deployed to production.
- **Changes:** Review publication writes/preserves an immutable compact companion and exposes its exact path; ordinary startup reads 689,992 bytes instead of the full 99,125,717-byte Review. Research/Watchlist load the pinned full source on demand. Archived links/legacy remain exact. No eager compact Kell fetch after startup.
- **Correctness:** account-specific watchlist caches, explicit anonymous import, remote-authoritative reconciliation and async owner guards; strict Kell schema/source/count validation; missing numeric values; full-history chart indicators before cropping; XNYS final-session calendar generated from pinned exchange-calendars 4.11.3 with standard-library production reads; prior-history boundary highs participate in weekly resistance. Null resistance never becomes a Blue sky claim. Accessible primary selection, collapsible EOD summary and direct Watchlist entry.
- **Methodology:** versioned future weekly output `weekly-birth-v2.1-resistance-boundaries`; read-only comparison on pinned baseline data retained in `docs/review/weekly-definition-comparison-20261026.json`, reproducible with `scripts/audit_weekly_review.py`. Available charts 2,176/2,615; archived score/stage/eligibility replay agreement 2,174. Replayed before/after top-15 equals the published top-15 in order; 36 resistance measurements change, 6 with score/stage/eligibility changes. No claim of improved returns. Existing snapshot/price/stage/outcome archives and Composite/Kell weight definitions are untouched. Calendar changes affect future terminal holiday weeks, not an invented historical backfill.
- **Tests at checkpoint:** 191 Python, 103 Node and 6 Chromium cases pass; additional legacy-mode unit and final targeted reruns in progress. Publisher regression executes the actual copy/reset/checkout/commit/push shell against a local temporary remote. Auth simulator checks deletion/token refresh/account changes/import without contacting real accounts. Build passed. No added scheduled scanner, provider call or sender toggle.
- **Files:** publication/frontend/watchlist/weekly/radar code and two existing workflows, focused tests, generated 21 KB offline calendar, one current 690 KB bootstrap companion/pointer, implementation/audit docs. Calendar generator dependency is development-only and pinned; production gains no package install.
- **Risks/next:** inspect PR CI and final validation, then post-merge verify Vercel's actual bootstrap/source requests and the next real EOD atomic publication. Previews rewrite data to the active production branch and cannot alone establish that the new compact pointer is live. Missing Oct15/19 sessions, corporate actions, independent Weekly outcomes and archive storage remain separate tasks.

- **Final local verification, 2026-10-26 13:42 UTC:** 191 Python, 104 Node and 6 Chromium cases pass; final 2 Review browser reruns also pass after the last source guards. Static build, workflow YAML and diff checks pass. Local 390px and 1440px screenshots show the 15 weekly cards, collapsed summary and direct Watchlist navigation without document overflow. No production rollout has occurred.

- **Visual follow-up:** wrapped the primary navigation on narrow screens so the direct Watchlist button is visible without horizontal navigation scrolling, and removed the residual “no nearby swing” label from old null-resistance cards. Added a browser visibility assertion for the Watchlist button.

- **Remote checkpoint, 2026-10-26 13:44 UTC:** implementation `800af98cb5fc15a84fc4934b618f75e81204d990` pushed and draft PR #69 opened against `feature/unified-review-grid-lab`. GitHub confirms MERGEABLE; validation run `40333107938` and Vercel preview are still in progress. Final narrow-screen navigation/label browser rerun passes (2/2). No production change.

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


## 2026-09-21 — Reliable review publication and delivery, phase 1

- Branch: `codex/reliable-review-refresh`. Implementation commit: `8463205dded0069903830e7ad785cde72fcdd405` (follow-up hardening and docs remain on this branch).
- Changes: One lab publication writer; removes Telegram credentials access and all sending from Trend Birth; calls tested publisher on lab branch.
- Validation: Workflow parsed locally; publisher/loader contract validated on companion lab branch; activation depends on that branch being promoted first.
- Scanner selection, rankings and scoring unchanged. No live Telegram message was sent; no production branch was merged or deployed by this implementation.
- Caveats: coordinated three-PR rollout required; ambiguous send needs manual reconciliation; per-mode metric separation and real dated AI review remain follow-up work.
- Next: review and activate in the order documented in `REVIEW_PUBLICATION.md`.


## 2026-09-21 — Phase 1 activated and verified

- Trend Birth PR #2 merged into the lab branch at `d88df04c65cfb6316d534607038410a880ad3fdf`.
- Trend Birth PR #3 merged into main at `1ecaa512f64da89353f379aa08c7730991309b04`.
- Unified PR #76 merged into main at `87f96d1759d8e2b919e72cc1fb99215f52c7ee41`.
- Both helper schedules were temporarily paused for activation and are now active. Normal Unified EOD scheduling was not changed.
- First production refresh: https://github.com/Garrincha077/StockScout-Trend-Birth/actions/runs/35650377382 — success; published data commit `5d757111398d192b85341f091f597246f40219a1`.
- Published Vercel deployment `dpl_3HMAjgKc1eXVWyYdVbaKDLK7Fuaa` succeeded. Public verifier checked the committed pointer, deployed hash, full chart coverage and active Unified run.
- Verified session `2026-09-18`, run `2026-09-18-eod-35425827607-1`: 82 candidates/82 charts, 5 Kell 3x, 5 gap candidates, 3 multi-hit candidates.
- Snapshot SHA-256: `a02793fc34805c2b1d3fac2acada5334ec758d626d669d0b086bf4e143b5abde`.
- Production notification dry-run: https://github.com/Garrincha077/StockScout-Unified/actions/runs/35650861821 — success. Reservation and send steps were skipped (`deliver=false`); no real Telegram message sent during validation.
- Repeat refresh: https://github.com/Garrincha077/StockScout-Trend-Birth/actions/runs/35650957544 — success, `changed=false`, no publication commit.
- Browser verification: permanent snapshot URL displayed the correct run and 82 candidates; Multi-hit displayed 3; chart click opened ticker detail; invalid snapshot URL showed an error without falling back to latest.
- Caveat: the roughly 5 MB monolithic snapshot was slow to load in the local in-app browser (eventually successful), while hosted verification completed in seconds. Splitting grid metadata from chart history is a useful next UX optimization.
- The scheduler-only PR has no `lab/` directory, so its Vercel preview failed with `NOW_SANDBOX_WORKER_ROOTDIR_NOT_EXIST`. The application branch deployment and both application CI checks passed; no hosting root setting was changed to accommodate an infrastructure-only branch.
- This supersedes the earlier pre-activation notes. New production messages use immutable URLs; ambiguous sends require reconciliation. Real AI review, per-mode metric separation, exact Bottom Telegram parity and lifecycle tracking remain subsequent phases.


## 2026-09-24 — Kell ML historical research lab v0.1

- Branch: \`feature/kell-ml-lab-v01\`. Research-only; no production cutover.
- Added \`research/kell_ml/kell_ml_v01.py\`: point-in-time feature extraction, benchmark-relative strength, conservative weekly context, EMA recapture/retest sequence proxies, Silver stage labels, forward outcome layer, chronological splits, baseline structure classifier, baseline opportunity classifier and candidate probability ranking.
- Added methodology/data docs under \`research/kell_ml/docs/\` and isolated CI workflow \`.github/workflows/kell-ml-lab.yml\`.
- Kell source discipline: Silver labels and every numeric threshold are explicitly StockScout project proxies, not published Oliver Kell rules. Gold human-reviewed frozen snapshots remain the intended structural ground truth.
- Leakage control: forward return/MFE/MAE fields are never in \`MODEL_FEATURES\`; weekly context cannot use later same-week sessions; chronological splits replace random row splits.
- Development bug found and fixed before PR: a first weekly aggregation approach treated a history truncated mid-week as if the partial week were complete. A future-mutation test caught the leak; v0.1 now uses conservative Friday closes pending an exchange-calendar adapter.
- Local validation on the fuller modular prototype: 7/7 tests passed after the fix. End-to-end synthetic dataset build processed 8,000 snapshots. Synthetic opportunity smoke test ran on 6,520 train and 1,180 evaluation rows.
- Important interpretation: near-perfect reproduction of deterministic Silver stage labels would be tautological and is **not** evidence that the model has learned Kell. Meaningful evaluation begins with Gold labels plus walk-forward/out-of-sample testing.
- Behavior/ranking impact: none outside the isolated research branch. Unified EOD, Trend Birth publication, existing StockScout candidate selection and Telegram workflows are untouched.
- Methodological caveats still open: survivorship-aware historical US universe, delisted symbols, point-in-time fundamentals, holiday-aware weekly bars, and Gold/hard-negative case creation.

**Next logical step**
- Connect a historical price + point-in-time universe source.
- Generate broad event/control cohorts outside current StockScout scans.
- Build the first 100–200 blind Gold/hard-negative snapshots.
- Only then compare Silver baseline vs Gold-trained structure model and run walk-forward opportunity/ranking tests.


## 2026-09-24 — Kell ML v0.1 historical seed + Gold-queue hardening

- Draft PR: #18. Branch remains research-only; no production scanner/ranking/publication/Telegram path is imported or changed.
- Added provider-neutral historical-panel CLI, historical event miner, deterministic blind Gold queue builder, retrospective winner/failure sampler (explicitly hindsight-only), Gold-label template/validation/merge path, and `train_structure(..., target_col="gold_stage")`.
- Historical event discovery is independent of the current StockScout scan and includes EMA recaptures, first retests, 60D breakouts, unusual volume, 5% gaps, EMA10 extensions, benchmark-relative-strength cases when benchmark data exist, and contracting structures near EMA20.
- Added a pinned public historical structure-only CI seed using `plotly/datasets` commit `0c447c47b757ad74edecab31f0d72f849d2e67c2`, blob `2a1f02e3675ad8bb6f3a8e536e15f601cfe32fbf`. CI deterministically samples 160 tickers by SHA-256 ticker order; selection does not use future performance.
- Public seed result: 197,099 daily rows from 160 stocks spanning 2013-02-08 through 2018-02-07; 180,740 historical event rows; 200-case blind labeling queue.
- Gold queue sampling bug found and fixed: the first global hash cut overrepresented generic contraction events despite per-bucket caps. Queue now round-robins across event-reason x year buckets. Verified balanced result: reasons 24-30 cases each; years 33-34 cases each.
- Chronological Silver structure-model smoke: train 113,134 rows (through 2015), validation 39,878 rows (2016), test 44,087 rows (2017-2018). Validation macro-F1 0.8769 / balanced accuracy 0.8715; test macro-F1 0.8735 / balanced accuracy 0.8581.
- Interpretation guardrail: those Silver scores measure reproducibility of deterministic StockScout/Kell proxy labels from overlapping features. They are **not** evidence of Kell skill, predictive edge, or opportunity-model validity.
- Real StockScout integration audit on 48 Review Grid candidates dated 2026-09-23 found and fixed mixed ISO/Unix chart dates and reinforced strict separation of structural stage from review/setup quality. Current review buckets on that sample: 4 PRIORITY_REVIEW, 18 STRUCTURE_ONLY, 22 WATCH, 3 PRICE_INELIGIBLE, 1 EXTENDED.
- Historical dollar-price leakage found and fixed: Kell's absolute $10 floor may not be applied to back-adjusted historical close. The feature now requires `close_raw`/`raw_close`; if absent, historical price-floor eligibility is unknown. The public structure seed therefore does not assert the $10 historical gate.
- Empirical source check: the Plotly seed shows split-normalized AAPL levels around the June 2014 7:1 split, reducing split-discontinuity risk for technical structure. The seed is still explicitly not treated as a survivorship-clean opportunity universe.
- Data-source audit: Alpha Vantage exposes historical listing/delisting status but the current free connection is rate-limited for bulk collection; Financial Datasets has no available credits; recent Alpaca IEX does not provide the needed deep-history bulk universe in this connection. QuantRocket's free 2007-2011 all-US learning bundle including later-delisted stocks is the preferred no-cost next broad survivorship-aware corpus if access is supplied.
- Latest research artifacts include the blind Gold queue, report manifest and serialized Silver structure model. Gold setup taxonomy is aligned with Work: READY, NEAR_READY, LEADER_WAIT, EXTENDED, REPAIR, REJECT.

**Next logical step**
- Acquire/connect a survivorship-aware bulk historical universe (preferred first no-cost path: QuantRocket US Stock learning bundle 2007-2011, or an equivalent provider).
- Run the existing provider-neutral corpus pipeline and generate the first 100-200 blind chart packets.
- Review/lock `gold_stage` labels without forward outcomes, train the Gold structure model, then compare Silver-vs-Gold errors chronologically.
- Only after that, build/evaluate the opportunity/ranking model on a survivorship-aware walk-forward dataset. Do not promote the current Silver model into production.

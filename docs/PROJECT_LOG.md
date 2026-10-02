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
## 2026-09-27 — One aligned LAB publisher for scheduled refresh

- Branch: `codex/trend-refresh-aligned`, based on controlled `main`.
- The scheduled Refresh workflow now dispatches `Unified Review Grid Lab` on the production feature branch. That workflow is the sole publisher: it syncs the owner watchlist, builds Review and compact Kell from one activated Unified manifest, validates identity, records the Weekly Birth shadow audit, and commits the aligned immutable bundle.
- The previous Refresh was a second publisher that updated only Review and the alert payload, leaving `kell-latest.json` and its companion on an older session and creating a race with the LAB publisher. The scheduler now has only `actions: write` permission and no checkout or data commit.
- An explicit workflow dispatch to a non-production topic branch was accepted for a read-only test. After merge, manually dispatch Refresh once and verify its triggered LAB run publishes matching session, run ID and Unified manifest hash.

## 2026-09-27 — Default-branch workflow watchdog

- Branch: `codex/trend-watchdog-main`, based on controlled `main`.
- Added a trusted `workflow_run` watchdog on the default branch so GitHub can observe failed Refresh, Review Grid Lab, and old/new PR validation workflows. It retries at most one initial transient Refresh or new validation failure, then records a deduplicated issue for persistent failures. It never checks out or executes failed PR code.
- Tests cover transient retry, second-attempt deduplication, and a code failure with no retry. No scan, publication, deployment or Telegram behavior changes.

## 2026-10-02 — Activation monitor and verified refresh

- Branch: `codex/eod-linked-refresh-20261002`, based on main `2a016ceb98e183782f517e386339d8f74d5204d0`; implementation/review commit is recorded by the accompanying PR.
- The scheduler checks activated Unified data every 15 minutes from 01:00 through 19:59 Europe/Zagreb, outside the ordinary evening EOD window. Existing low-frequency slots remain; the 17:17 slot forces daily tracked-watchlist enrichment. GitHub schedule queueing can add delay.
- A pinned NYSE calendar requires the latest actual completed session, including holidays/early closes. The controller verifies all three Unified mode hashes and identities, compares the committed/deployed Review pointer and source-manifest hash, starts only the sole LAB publisher when needed, reuses an in-flight publisher, and waits for successful publication/deployment. A stale upstream fails visibly.
- Manual historical recovery may explicitly pin a completed source session/run. Topic-branch runs are read-only. The controller has no Telegram credentials or sends; it downloads small pointers rather than chart archives on every probe.
- Repeated stale probes do not add comments to an already open watchdog incident. Code, publication and other failures retain normal reporting.
- Affected: Refresh workflow, refresh controller, dedicated calendar lock, refresh/watchdog regression tests, watchdog helper and this log. No discovery fields, signals, scoring, rankings, watchlist selection or sole-publisher data contract changed.
- Local validation: calendar, stale-alignment, mode-hash, exact-source, no-op, duplicate/in-flight publisher, deployment-lag, failed/ambiguous dispatch and dry-run contracts pass. Companion Unified root suite: 244 passed / 2 existing documented skips; Ruff and shell/YAML checks pass. Remote branch and production results remain to be recorded after validation.
- Limits: this uses a bounded polling bridge instead of an assumed cross-repository credential. The optional Unified recovery token can dispatch immediately; without it, recovery waits for the monitor. Public pointer convergence is checked here; immutable archive/chart validation remains in the LAB publisher and Unified delivery verifier.
- Next: confirm branch dry-run and production no-op, then record exact run IDs; future authenticated direct activation events can supplement this monitor.

### Activated verification

- PR #40 merged as `c5833a06738175b01cc58cba0bf663fd5118e6bb`; review head `b974caa8610390e08036e41277b2c26f7a6af6a2`. Review run `36987780207` and main run `36988408129` passed all 16 contracts and live freshness verification for `2026-10-01-eod-36981190571-1`, source manifest SHA `dd07a485dddebb92fa9638cf23ef31ab6e0613b9ec1a5011eb5cec887ced8226`. Both were no-ops with `dispatched=false`.
- Unified PR #102 merged as `dd8454edd907c546c0d87cbcae2d32a7df42328c`; CI `36987955750` and coordinated no-send Morning Recovery `36988467203` passed. Its GridView verification run `36988482782` passed with reserve/send steps and stage-delivery job skipped.
- Vercel confirms preview `dpl_Hc9JhEahtEXP4sTJmDVevMJBZQqE` failed only because this scheduler branch has no configured lab Root Directory (`NOW_SANDBOX_WORKER_ROOTDIR_NOT_EXIST`). Production app remains on the existing feature branch; the deployed pointer, immutable archive and charts were independently verified.
- Deployment settings were not changed to make an infrastructure-only branch look like an app. The actual activation-monitor job is green on main. New-source dispatch/wait paths are covered by regressions; production exercised the already-aligned path.

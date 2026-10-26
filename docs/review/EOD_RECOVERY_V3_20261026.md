# Deployment verification and isolated EOD recovery V3

Verified 26 October 2026, 14:50 UTC. Related issue: #62; this comparison does not close the migration issue.

## 1. Application fixes are deployed

[PR #69](https://github.com/Garrincha077/StockScout-Trend-Birth/pull/69) passed GitHub validation and Vercel preview, then merged as `d1711e408eea0cb3164494a5f2c6d794be0e587f`. The existing publication workflow `40339525673` completed its **build/publish job successfully**, including snapshot generation, preserved bootstrap files through Git reset, Review/Kell identity validation and publication. Its separate historical-calibration job was still running at the verification checkpoint; build success is not a claim that the whole workflow had finished.

The resulting data commit is `82b652f6f2aef13d5617dfcee48ff3aae1d38d7a`, production deployment `dpl_9FGLTCkgM8txqEacvaaWYCAsmQ46` **READY**. [Production application](https://stockscout-trend-birth-review-lab.vercel.app/).

Fresh headless Chromium checks of desktop, 390px mobile viewport and Statistics observed no JavaScript errors or HTTP error responses. Weekly/Kell switches and candidate detail worked; 15 Weekly and 5 Kell cards were shown. Startup requests included publication, intelligence, quality history and the advertised immutable bootstrap; neither the full Review nor Kell dataset was fetched at initial load. The bootstrap measured **689,992–693,392 decoded bytes** and **243,500–245,463 encoded bytes** across the publication refresh, compared with the former 99,125,717-byte decoded snapshot. This verifies payload behavior, not a real-phone latency percentile. No document horizontal overflow was observed.

The latest source session remains **23 October**, run `2026-10-23-eod-40042215150-1`. Verification happened during the next trading day, before its EOD existed. We verified a real publication refresh on the existing EOD, not a future October 26 close. Login with a real owner account on a physical phone was not performed; authenticated-state tests remain local simulations. Anonymous production loading and owner-client initialization were exercised.

## 2. Recovered source evidence

Original Unified ZIPs remain in the existing draft release **423075292**, with original byte size, SHA256, ZIP CRC and all four source run/date manifests verified independently. Raw ZIPs and tar files are not committed to Git or deployed to Vercel.

| Session | Original run | ZIP SHA256 | Recovered evaluable stage/close rows | Unavailable source charts |
|---|---|---|---:|---|
| 2026-10-15 | 38825335004 | `b8595b0e05da8d41cf8523b94b5d799a7e911efa697206cf84c97ed4e4f25e7a` | 2,646 | QRVO, TJGC |
| 2026-10-19 | 39347937228 | `5e7041b976d902d12f6f5e84d84591d230ed9ee9e10df805e198cca41c9cf103` | 2,602 | HNST, QRVO |

The recovery reuses the production scalar merge, original mode membership and Next → Ryan → Bottom chart priority. Where a tracked ticker falls outside the candidate union, only that original Pages bundle's Bottom charts may supply it. Missing/stale charts remain unavailable; there is no present-day Yahoo fallback, guessed price or zero-filled return. Future, unordered and duplicate chart dates are rejected.

The frozen daily radar SHA256 is `94b5d96166c7366ae9e394ebc5f2a20bb75c46620017f97775827734ff182aa4`. GitHub independently confirms those exact bytes at the pre-session 24 September commit `82ce536f700d2159fe84ec33e9d5b38cdda44ba8`, as well as the pinned baseline `168fc51`. Date parsing is memoized without changing its pure result. No Weekly/Kell ranking is recomputed by this recovery tool.

### Historical owner-state limitation

The checked-in `tracked-watchlist.json` containing only CLOV is **not** the actual runtime owner input. The old workflow also read the private owner watchlist. We therefore extracted tracked membership from authentic, earlier Review snapshots dated **14 October** and **16 October**, with original full-snapshot SHA256 recorded in the adjacent `tracked-observed-*.json` files. Both observed snapshots list the same 16 tracked symbols.

V3 uses the **last observed prior EOD** list for each missing date. It does not assert that no owner edit occurred between those observations and the missing session. Every recovered input explicitly sets `trackedMembershipExactOnRecoveredSession:false` and `observedByTrendBirthOnSession:false`. This limitation blocks silent migration/calibration. It is not repaired by borrowing a later watchlist.

## Before/after comparison

The baseline is reproduced from the immutable V2 stage and close inputs before inserting any recovered date. All published horizon/stage counts and values, total transitions and coverage diagnostics must match exactly or comparison stops. SHA256 values of **seven V2 files**—monthly stages, closes, outcomes and the report—are checked unchanged after replay.

| Metric | Observed V2 | Reconstructed V3 |
|---|---:|---:|
| Archived exchange sessions | 20/22 | 22/22 |
| Valid EOD source quotes for evaluated rows | 52,951 | 58,199 |
| Stage transitions | 5,728 | 6,156 |
| Matured 5D events | 4,368 | 4,676 |
| Available 5D outcomes | 3,255 | 4,567 |
| Missing matured 5D outcomes | 1,113 | 109 |
| 5D coverage | 74.52% | 97.67% |
| Matured 20D / 60D outcomes | 0 / 0 | 0 / 0 |

Inserted dates cause **803 added** and **375 removed** event identities, plus **298 changed predecessor links** on shared identities. **1,014 shared event outcome records** change. V3 rebuilds event membership and maturity from scratch; it never inserts two rows into the existing immutable event archive or reuses incompatible old outcomes.

All 109 remaining missing matured 5D outcomes are missing ticker quotes on otherwise available sessions; whole-session gaps are zero in this reconstruction. Universe rotation and unavailable charts still matter. “100% source quote coverage” applies only to the declared evaluated rows, not all possible equities or every later exit.

| Entered radar stage | V2 5D n / coverage / mean | V3 5D n / coverage / mean |
|---|---|---|
| 0/4 | 767 / 71.55% / −0.196% | 1,168 / 97.50% / −0.292% |
| 1/4 | 973 / 74.22% / −0.944% | 1,340 / 97.74% / −1.196% |
| 2/4 | 475 / 75.04% / −0.906% | 654 / 96.46% / −1.320% |
| 3/4 | 536 / 75.60% / +0.023% | 728 / 97.85% / +0.039% |
| 4/4 | 504 / 78.38% / +0.206% | 677 / 98.83% / +0.330% |

These means are descriptive, with changed membership/coverage and overlapping events; they are not evidence of a more profitable model. Corporate-action adjustment, delistings, longer maturity and independent holdout remain unresolved. Every V3 horizon/stage explicitly remains ineligible for calibration.

## Artifacts, reproduction and rollback

- Committed isolated inputs: `lab/data/recovery-v3/2026-10-15.json`, `2026-10-19.json`.
- Machine-readable event/value comparison: `lab/data/recovery-v3/comparison.json`.
- A separate local ZIP contains full V3 monthly stage/price/outcome outputs and the comparison; no original source ZIPs, credentials or browser state are included.
- The production V2 pointers, data files and Statistics source are unchanged by this recovery. V3 schemas cannot silently replace V1/V2 archives. The recovery code is a manual offline CLI; no new schedule, sender, scanner or API is introduced.

To regenerate missing inputs, download the exact existing release assets and export the frozen radar with `git show 168fc51:scripts/trend_birth_radar.py`. Use the adjacent verified prior-watchlist files:

```bash
python scripts/recover_trend_birth_eod.py \
  --artifact /tmp/unified-eod-2026-10-15-pages.zip --session 2026-10-15 \
  --radar /tmp/frozen-radar.py --tracked docs/review/tracked-observed-2026-10-14.json \
  --output /tmp/recovered/2026-10-15.json
# Repeat for Oct19 using tracked-observed-2026-10-16.json.

python scripts/compare_trend_birth_recovery.py \
  --stages lab/data/trend-birth-ticker-history \
  --prices lab/data/trend-birth-price-history \
  --baseline-report lab/data/trend-birth-stage-forward.json \
  --recovered lab/data/recovery-v3 --output /tmp/new-isolated-v3 \
  --baseline-commit d1711e408eea0cb3164494a5f2c6d794be0e587f
```

Use the baseline input hashes in the comparison to select the same observed archive version. The comparator refuses an existing output or any output overlapping its inputs. Recovery refuses an existing recovered file. Rollback is simply to keep serving V2; V3 has no active production pointer. Do not close #62 or promote V3 until the tracked-membership policy and remaining quote/methodology gaps are reviewed.

Verification: **198 Python tests pass**, including seven focused recovery cases covering offline source merge, future/stale rows, provenance tampering, event reconstruction and unchanged baseline bytes. Existing PR #69 validation additionally passed 104 Node and 6 Chromium cases. Actual production browser checks are described above; no real owner emails or database mutations were performed.

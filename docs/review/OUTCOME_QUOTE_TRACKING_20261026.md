# Retain outcome closes after candidate eligibility ends

Implementation checkpoint: 2026-10-26. Topic `feature/retain-outcome-quotes-20261026`, based on production documentation `b3fa64c` / implementation `2008e44`. Implementation is locally tested; deployment is recorded separately below.

## Problem and source check

A deterministic audit of frozen V3 through Oct23 reconciles 4,676 matured 5D events, 4,567 available and 109 missing, involving 66 tickers. 107 missing events have a required ticker/date outside the day's stage universe; two have explicitly unavailable technical evaluation (QRVO Oct6, TJGC Oct15). These correspond to 118 distinct missing ticker/date prices and 126 endpoint references. Missingness may bias returns; it does not establish a delisting or absence of market trading. Evidence is retained locally in `/workspace/trendbirth-review-2026-10-26/missing-v3-audit/` with the executed notebook, script, two CSVs and per-input SHA256.

The current V2 event history implies 1,177 still-open ticker histories. Oct23 primary prices cover 1,122 of these; 55 are outside that evaluated-only archive. The verified Bottom chart manifest supplies just one of the 55. Its chart scope is essentially the current scanner pool (2,053 names), so storage alone cannot solve price availability. Both existing Yahoo chart hosts returned HTTP200 for a sample TSEM request during Oct26 market hours; the new capture logic correctly rejected the still-open session. No source quote from that probe was persisted or used as an EOD.

## Smallest operational change

- Derive the tracking set from existing permanent stage transitions; no user-maintained second watchlist. Keep each ticker through next-session entry plus 60 complete exchange sessions. Several open transitions share one daily quote.
- Reuse original evaluated-only closes whenever present. Fetch only missing tracked ticker closes, using the Yahoo chart provider already used by the application's tracked-symbol fallback. Four workers; two known hosts; 10-second request timeout. No new API key, scan schedule, database, Google Sheet or cross-repository change.
- Collect at least 20 minutes after scheduled XNYS close (to let delayed daily feeds settle), and only while New York's calendar date equals the target session. Validate exact ticker, USD, New York venue, regular-trade date, no future bar, positive finite quote and agreement of reported regular price with the day's unadjusted close. Observation time is receipt time; record provider, host, ticker, price basis and trade/receipt timestamps. No dividend adjustment. Corporate-action quality remains uncertified.
- Freeze activation at **after 2026-10-23**. No new provider calls may backfill Oct23 or earlier. Initial health is honestly `waiting-for-next-session`; 55 currently absent quotes are not magically recovered. The old 109 V3 outcomes remain a separate historical task.
- Store supplemental observations in small separate `trend-birth-outcome-quotes/YYYY-MM-DD--<canonical-sha256>.json` files. Anchor them to policy hash, source run/date/Unified SHA and exact canonical primary price-point digest. Existing primary archives are unchanged.
- A retry fetches only still-missing tickers. Successful prior prices/provenance cannot change. Improved coverage creates a new content-addressed observation; the old file remains. Repeated failures or already-complete observations create no extra files.
- Forward maturation merges these additional closes only for outcomes. Stage membership, candidates, scores, rankings, market internals and Composite formulas are unchanged. Evaluated-universe source coverage keeps its original denominator; tracked supplemental/missing counts are displayed separately in Statistics. No zero-filled prices/returns, no calibration approval or V3 activation.
- The existing daily workflow retains the new archive and compact health across its Git reset, publishes them atomically with the forward report, and validates current tracking demand/source/health before commit. Absent or inconsistent tracking evidence blocks publication; unavailable individual prices remain explicit.

## Verification

- 212 Python tests, 108 Node tests and 10 Chromium cases pass. Six new Python cases cover the exact 60D retirement boundary, dropped-universe 5/20/60D maturation, primary-byte immutability, no pre-activation/provider-history calls, provider rejection rules, missing quotes, content-hash tampering and append-only retry/idempotence. The actual production publication shell still passes all six temporary-Git-remote regressions with supplemental files included.
- The real Oct23 replay reproduces **every original V2 report field exactly**, excluding only the additive tracking health metadata. Original 5D count remains 3,255 and transitions 5,728. The real EOD gate passes against that replay (2,614/2,614 evaluated prices, expected/current Oct23).
- Provider samples during open market: both hosts HTTP200, capture correctly denied before close. This is a reachability/schema check, not a verified future closing observation. The next real source EOD and same-day quote capture must be checked after publication.
- Browser regression shows supplemental quote counts/missingness independently of primary source coverage, retaining the existing 15-row outcome table. Existing V2/V3 comparison, mobile and simulated auth cases pass. No real account writes or emails.

## Reproduction and rollback

```sh
python scripts/outcome_quote_tracking.py
python -m unittest discover -s tests -p 'test_outcome_quote_tracking.py' -v
```

The pipeline passes four explicit tracking options to `trend_birth_stage_forward.py`: tracking directory, policy, exchange calendar and health. Existing standalone callers without options retain the old behavior. Existing recovery V3 scripts and frozen files are untouched.

Rollback: revert this feature through a reviewed PR, retaining additive observations for evidence. Do not rewrite prices or already-matured event archives. No database/Sheet migration is required. The USD/New York provider guard intentionally leaves unsupported symbols or unavailable quotes missing; corporate actions and delisting treatment still require their own versioned audit before return-based calibration.

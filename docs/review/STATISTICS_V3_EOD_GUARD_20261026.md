# Statistics V3 comparison and EOD publication guard

Implementation checkpoint: 2026-10-26 18:20 UTC. Topic `feature/statistics-v3-eod-guard-20261026`, based on production publication `340b8c67678849cf046804eae1cfa21a8a7a6ed4`. This checkpoint describes locally verified implementation, not a deployment claim.

## User-visible behavior

- Statistics retains the existing live V2 outcomes. An expandable comparison loads `data/recovery-v3/comparison.json` only when opened. Both comparison columns are frozen at 2026-10-23, even when the live V2 report later advances. No reconstructed data is mixed into Market Internals, Composite, Thermometer or ranking.
- Coverage table: V2 20/22 sessions and 3,255/4,368 matured 5D outcomes (74.52%); V3 22/22 and 4,567/4,676 (97.67%). Missing matured outcomes 1,113 versus 109. The 5D/20D/60D selector compares stage samples, pending counts, missing reasons, coverage, mean and median. Immature results show unavailable values, not zero returns.
- The panel labels recomputed sessions, uncertain intervening owner watchlist membership, corporate-action/delisting and independent-validation limitations. It does not activate V3 or approve calibration. Retrieval/schema errors leave the V2 report available and permit a retry by reopening the panel.
- Review and Statistics show the last checked publication date and the expected completed session. Stale data receives a visible warning; missing/expired calendar or unavailable requests explicitly leave freshness unconfirmed. This is checked at page load, not a claim of continuous monitoring.

## Gate and calendar policy

`validate_eod_publication.py` executes after the publisher restores generated files across Git reset/checkout and **before Git add/commit/push**. It checks:

1. Source is a completed XNYS session and is no older than the latest due session.
2. Review bytes match the publication SHA256; run/date/Unified identity also match Kell.
3. The current full-universe stage archive equals the Review index; current archived closes equal prices extracted from that same Review input.
4. At least 99% of currently evaluated tickers have valid archived closes. This is a source quote threshold, not a threshold for matured forward returns or a certification of the whole universe.
5. Since the previously published session, no new exchange session is absent from the quote archive. Existing historical October gaps are not silently rewritten.
6. Market Internals, Composite latest/history and stage-forward reports agree on the EOD date; Market Internals also agrees on run ID.

A failed check exits the existing workflow before a publication commit. The remote's last valid commit remains served. No additional scanner, API provider, scheduled workflow, email, Telegram send or database mutation is introduced. Workflow logs retain the exact failure; the UI describes datedness, not a specific unobserved workflow failure.

The shared 64,891-byte `lab/data/exchange-sessions-v1.json` contains 1,505 XNYS sessions for 2025–2030, with actual scheduled UTC closing times (including holidays, early closes and DST). Policy allows **four hours after each close** before that session is due. A completed new EOD can publish earlier during this grace period. This is an explicit publication-service allowance, not the exchange's closing time. At a regular 20:00 UTC close the deadline is 00:00 UTC; at 21:00 it is 01:00; a 18:00 early close is due at 22:00 UTC. Outside the calendar's support range the gate fails and the UI reports unknown freshness.

Rebuild only during development:

```sh
python -m venv /tmp/trendbirth-calendar
/tmp/trendbirth-calendar/bin/pip install exchange-calendars==4.11.3 pandas==2.3.3
/tmp/trendbirth-calendar/bin/python scripts/generate_eod_calendar.py
```

Production and CI only use stdlib Python and browser JavaScript to read the committed calendar; no calendar package is added to runtime dependencies. Calendar rules need review and regeneration if the exchange announces changes or before 2031.

## Validation

- Full existing suite plus initial additions: 203 Python tests; 107 Node tests; 9 real Chromium cases passed. Three further publication regressions (mixed source run, skipped new session, matching but insufficient close coverage) pass independently; CI reruns the final full suite.
- Publication integration executes the actual production shell against a temporary local bare Git remote. A valid complete bundle commits/pushes; stale Composite, wrong current quote archive, mismatched source run, skipped new sessions and below-99% matching quotes do not create a new publication commit.
- Python and Node verify Friday/weekend/Monday boundaries, Thanksgiving early close, DST and expired-calendar behavior.
- Real retained EOD gate passed 2026-10-26 18:16 UTC: session 2026-10-23, run `2026-10-23-eod-40042215150-1`, 2,614/2,614 evaluated quotes. At that timestamp Oct23 remained the latest due session. This is not an Oct26 EOD verification.
- Mobile browser verifies lazy comparison, common date, immature 20D nulls, unchanged V2 table, no document overflow, 503 retry and visible stale warning while V2 remains usable. All prior chart/calendar and Review/auth simulation cases pass. Physical-phone real-owner sign-in remains unconfirmed.
- Static UI build, JavaScript syntax and diff whitespace checks pass. V2 monthly archives, recovered V3 JSON, scoring formulas/weights and selection pointers are unchanged.

## Rollback

Revert the UI/gate implementation commit through a reviewed PR. V2 continues as the default throughout; no history migration or pointer reversal is necessary. The compact calendar can remain as an unused additive file. Do not bypass a genuine gate failure: inspect the dated source bundle and repair the missing/mixed inputs with provenance before retrying.

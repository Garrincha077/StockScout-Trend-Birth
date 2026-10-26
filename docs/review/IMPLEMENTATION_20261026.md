# Trend Birth review corrections — 26 October 2026

Branch: `fix/trendbirth-review-20261026`; baseline `168fc51bfc207e134d29e6b30201e7c087c3c1d8`.

## Implemented

- **R1:** publication now writes an immutable `review-bootstrap-v1/<reviewSnapshotId>.json` and an additive `bootstrapPath` in the existing publication pointer. The ordinary Weekly/Kell Daily startup reads this file. Research and Watchlist fetch the original exact full snapshot on demand; Kell data is not eagerly fetched and an already loaded full Review supplies its embedded Kell rows. Archived snapshot/date links and legacy mode retain their existing source selection. Missing/invalid advertised bootstrap is an error, never a silent jump to a different publication. The production publisher preserves bootstrap files across its Git reset and commits them with their pointer.
- **R2:** older history's boundary highs now participate in resistance detection, including monotonic declines without an interior swing high. The weekly model is labeled `weekly-birth-v2.1-resistance-boundaries`. New output records resistance status, observed window and pivot reference. UI no longer turns a null measurement into “Blue sky”; older snapshots without those fields show unconfirmed resistance. A new historical maximum claim is not inferred.
- **R3:** normal reconciliation loads remote membership. Importing anonymous local tickers is a separate, explicit button. Anonymous and account-specific caches have separate keys. Session changes are checked around asynchronous reads/imports/writes; local metadata is retained on refresh to avoid storage-event churn. Regular login/token refresh cannot re-add a remotely deleted ticker.
- **R4/R5:** Kell loading requires a recognized compact schema, matching count and source identity; missing activation hashes are rejected when the Review has one. Numeric formatting distinguishes missing values from real zero. Recognized older compact versions remain explicit compatibility paths.
- **R6:** both weekly classifiers consult a versioned offline XNYS final-session calendar for 2000–2030, generated once with `exchange-calendars==4.11.3`. It includes holiday-shortened weeks. Production uses only the standard library: no new API, cron, provider call or runtime dependency. Outside the covered weeks the former conservative Friday behavior remains. Regeneration is a development operation, not an EOD step.
- **R7:** canvas indicators are computed over all available chart rows, then cropped with their candles. The chosen viewport no longer changes the seed of overlapping EMA values or drops already warmed-up SMA points.
- The initial EOD summary is collapsible, Watchlist has a direct navigation button, active primary views expose `aria-pressed`, and detail labels distinguish the Daily radar from Weekly structure.

## Measurements and model comparison

The baseline initial full snapshot is **99,125,717 bytes**. Its compact companion is **689,992 bytes**, **242,095 bytes with Python's gzip**. This is approximately a **99.3% reduction in decoded startup JSON**; the original cloud live measurement was about 31.8 MB compressed. Gzip sizes are payload measurements, not a promised latency or a Vercel transfer measurement of the new code. The small existing intelligence/history files are additional. Full Research still intentionally downloads the original large snapshot when requested; decomposing that research dataset and migrating multi-GB archives remain separate work.

The compact file copies the exact existing 15 Weekly and 5 Kell selections and their evidence/available bars. It does not re-run a scanner or rewrite their archived scores. Future EOD generation will use the corrected weekly definition. The existing full snapshot and historical archives remain unchanged.

[Comparison JSON](weekly-definition-comparison-20261026.json) is a read-only replay of retained chart rows at the pinned baseline. There are **2,176 available chart histories out of 2,615 indexed tickers**; **2,174** replay the archived score/stage/eligibility exactly. Those two differences limit claims about exact full-universe reproducibility from the retained charts. Replayed before/after top-15 lists both equal the published top-15, in order. **36** ticker resistance records change, including **6** with score/stage/eligibility changes. This is an algorithmic correction audit, not evidence of improved future returns or a historical return backtest.

To reproduce:

```bash
git show 168fc51:scripts/weekly_birth.py > /tmp/weekly-before.py
# Export that same commit's latest.json outside the working tree first.
python scripts/audit_weekly_review.py --snapshot /tmp/latest.json \
  --before /tmp/weekly-before.py --source-commit 168fc51bfc207e134d29e6b30201e7c087c3c1d8 \
  --output /tmp/weekly-diff.json
```

Calendar regeneration uses the exact pinned optional development package:

```bash
python scripts/generate_market_week_calendar.py
```

## Verification and rollout boundaries

Python and Node regressions cover the actual publisher reset/commit/push shell using a temporary local Git remote, compact/source identity and archive preservation, the resistance boundary case, holiday vs ordinary Thursdays, account cache isolation, and the actual renderer's warmed-up indicator values. Browser tests cover bounded startup/no eager full download, mobile card visibility, source switching and exact Research loading, remote deletion/token refresh/account switching/explicit import, and the four existing Statistics cases. Auth uses a local simulator: no real account, email, database write or Telegram send is performed.

The Vercel data rewrite points to the active production branch, including for branch previews. Therefore local tests of the committed bootstrap are the new compact-data verification; a branch preview can still consume the older production publication until merge. After a reviewed merge, verify the live publication advertises `bootstrapPath`, the compact file matches its source and ID, no full snapshot/Kell request occurs at ordinary startup, and an explicit Research click loads the pinned full source. Verify the next real EOD preserves the compact pointer through the publisher reset.

Rollback: revert the topic implementation and publication-pointer additions; full immutable snapshots remain available. No archive deletion/migration, missing-session reconstruction, Composite recalibration, sender toggle or cross-repository change is included. Missing 15/19 October sessions, corporate-action/delisting quality and a dedicated Weekly outcome study remain open follow-ups.

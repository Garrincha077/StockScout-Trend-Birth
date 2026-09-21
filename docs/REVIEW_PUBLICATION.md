# Verified review publication v1

The lab reads one healthy Unified activation. It verifies each mode manifest's
hash, run ID and session date, verifies JSON core/screener asset hashes, and
checks the root activation again after the build. A failed check leaves the
previous publication intact. Chart shards retain their existing reader; this
change does not claim per-shard cryptographic verification.

`publish_review_snapshot.py` validates candidate counts, unique tickers and full
chart coverage. Empty scans are valid. It serializes deterministic JSON and
publishes `data/snapshots/<runId>--<sha256>.json`. Identical reruns are no-ops;
changed analysis or inputs produce a different snapshot, even on the same day.
Existing snapshots and existing `history/<date>.json` links are never overwritten.
`latest.json` remains a compatibility copy; `publication.json` is the new pointer.
All files must be committed and deployed together.

Permanent links use `?snapshot=<runId>--<sha256>`. A missing archive displays an
error, never another session or raw GitHub fallback. Legacy `?date=` remains
supported and now pins the first archived version of that date.

The only writer is the default-branch refresh workflow, checking out the lab
branch. The old branch cache workflow is now read-only artifact validation.
Default builds no longer inject `analysis.example.json`; no daily AI review is
claimed. Deterministic review remains available without an AI overlay.

## Notification ownership

Unified is the sole Telegram sender. It compares the committed publication
pointer with the deployed pointer, verifies archive bytes and counts, checks the
snapshot-aware UI assets and matches the active Unified run. Timing alone never
establishes readiness. The lab has no Telegram send path or credentials access.
Every Telegram link pins the checked snapshot.

Unified reserves a session in its operational delivery ledger and pushes that
reservation before sending. It then performs one Telegram request and records
the receipt. Reserved or uncertain outcomes block automatic retry for that
session. A crash can require manual reconciliation; this is at-most-once
automatic sending, not a promise of exactly-once delivery.

## Rollout dependencies

There are three independent review branches:

1. Trend Birth `codex/reliable-review-publication` targets the existing lab branch.
2. Trend Birth `codex/reliable-review-refresh` targets `main` and removes lab sending.
3. Unified `codex/reliable-gridview-delivery` targets `main` and owns verified sending.

For controlled activation, temporarily disable the two old scheduled workflows
(lab refresh and Unified GridView Telegram), let in-flight runs finish, then merge
the lab change followed by its scheduler change. Re-enable/run lab refresh and
verify the deployed v1 pointer, immutable URL and matching run. Merge the Unified
change, run its manual default dry-run, then re-enable scheduled delivery. Do not
enable `deliver` during smoke tests. No activation or real Telegram test is part
of the implementation PRs. Keep other Unified EOD workflows running.

If reverting, keep published archives and the snapshot loader: deleting them
would break historical links. Disable the new sender before reverting its code.

## Deferred work

This phase does not change rankings, scan selection, mode metric merging or
entry labels. Follow-up work should separate per-mode price bases, expose the
exact Telegram candidate export, and add dated AI overlays and lifecycle history.
The Bottom lab selection remains a public-data proxy for the private digest.

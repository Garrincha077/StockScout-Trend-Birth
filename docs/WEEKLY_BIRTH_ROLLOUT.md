# Weekly Birth v2 rollout and rollback

The Review Lab builds `weeklyTrendBirth` (at most 15 names) and `kellDaily`
(at most five names) from the same activated Unified manifest. Existing
`unifiedCandidateIndex`, `candidates`, `kellCandidates`, and historical
snapshots remain readable. The legacy Trend Birth 0–4 evidence and messages
remain available during the comparison period.

## Shadow gate

Keep Unified repository variable `TREND_BIRTH_ALERT_MODE` unset while
collecting five distinct market sessions. The GridView summary retains its
legacy path; stage-change and hourly send jobs stay off. The Review Lab can
show the new lists without sending them. For each session record source
`sessionDate`, Unified manifest hash, publication hash, list counts, stage
counts, rejected-reason counts, and the weekly membership diff versus the
previous session. Inspect at least 25 distinct weekly charts across the five
sessions. Check the base boundaries, MA cluster, prior swing resistance,
extension, and breakout age on each. Reject release if the rules routinely
surface mature trends or resistance directly overhead. A short or empty list
is valid; do not fill it to a quota.

`lab/config.js` selects the default GridView mode. `weekly-v2` opens Weekly
Birth on a five-year weekly chart; Kell Daily and Research Universe are
separate tabs. `?mode=legacy` previews the old default. Old snapshots without
v2 shortlists fall back to Research Universe.

## Enable after the shadow gate

Record the current production branch, deployment ID and URL before any
Vercel change. Deploy the validated Review Lab commit and verify the deployed
`publication.json` matches the committed publication and activated Unified
manifest. Set the Unified repository variable `TREND_BIRTH_ALERT_MODE` to
`weekly-v2` only after that check. The two grouped messages use separate
idempotency keys; the first v2 session is baseline-only. The scheduled hourly
watch then only evaluates the current Kell Daily shortlist. Never run the
legacy stage-change sender and v2 sender together.

## Roll back

1. Set Unified `TREND_BIRTH_ALERT_MODE=legacy`. This switches future
   stage-change and hourly messages back to the legacy series. Confirm the
   scheduled jobs see this variable before a send window.
2. Set `lab/config.js` `defaultMode` to `legacy` and deploy it. The URL
   `?mode=legacy` is an immediate read-only preview of the fallback.
3. Verify one dry-run GridView probe, stage-alert selection, hourly selection,
   and legacy UI against an old snapshot. If the new deployment itself is
   unhealthy, restore the recorded known-good Vercel deployment and recheck
   `publication.json` identity.
4. Keep immutable history and receipts. Rollback only changes future display
   and future sends; Telegram messages already delivered cannot be recalled.

Do not promote or merge a rollback that removes v2 evidence from historical
snapshots. A delayed Vercel deployment is a deferred probe, not a failure to
repair by sending from the repository artifact.

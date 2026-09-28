# Weekly Birth A–D tiers — shadow hypothesis

Date: 2026-09-28. Branch: `codex/weinstein-weekly-birth`. These tiers are **quality/research labels**, separate from the existing `Long Base` → `Trigger` lifecycle stage. They do not change Unified candidate generation, Weekly Birth eligibility, or the Telegram sender.

| Tier | Membership | Use |
| --- | --- | --- |
| A | Already `weeklyBirth.eligible`, with ≥52W base, ≤6% weekly MA spread, ≤14% prelaunch 12W close range, ≥20% pivot-based runway or verified blue sky, price −5% to +3% from pivot, extension −6% to +6%, and passing RS-improvement, MA-turn, no-chase and extension checks. | Higher-conviction *structure* among confirmed names; stage still says whether it is prebreakout or triggered. |
| B | Other `weeklyBirth.eligible` names. | Confirmed by the existing v4 model, but without every A quality condition. |
| C | Non-eligible **Bottom Fishing** member, Crash Base or otherwise, passing the former Early Base Watch numeric bounds. | Up to five chart-review candidates, never an alert. |
| D | Non-eligible Bottom member that misses C but passes a broader measured-base guard. | Up to 25 additional lower-confidence chart reviews, never an alert. |

C requires at least a 52W base; weekly MA spread ≤8%; 12W prelaunch close range ≤30%; prior 13W SMA30 rise ≤4% and pre-base 26W SMA30 rise ≤8%; Mansfield RS ≥−5% and four-week change ≥−2 points; price −20% to +4% relative to pivot; ≥12% pivot-based overhead runway or verified blue sky; extension −6% to +10%; current four-week SMA30 change −0.5% to +2%; and eight-week launch advance ≤15%. It no longer requires the Crash Base detector. All inputs must be measured. A Bottom membership flag is required even when the preferred weekly chart came from Next/Ryan.

D permits a 39W base, MA spread ≤10%, 12W range ≤35%, prior 13W SMA30 rise ≤8% and pre-base 26W rise ≤15%, Mansfield RS ≥−10% and four-week change ≥−5 points, pivot distance −25%…+5%, ≥8% pivot-based overhead runway or verified blue sky, extension −10%…+12%, current SMA30 change −1.5%…+2%, and launch advance ≤15%. It is intentionally a **discovery queue**, not a substitute for an improving-RS signal. Crash Base names come first, then improving four-week RS, then proximity to the pivot and shelf tightness. Candidates failing D stay in Research Universe only; neither queue is padded.

The C and D queues are mutually exclusive. Both expose the existing Weekly Birth rejection reasons, the Bottom/Crash Base provenance and five-year weekly charts. Old snapshots without these lists remain readable. The v2 alert builder reads only `weeklyTrendBirth`, so C/D membership cannot create a weekly Telegram message.

Offline replay against the exact activated 2026-09-25 Unified manifest (`8148312d9bf9953acf26e4ec7120f2df9e32b0ae7114355846b6681d269002a4`) yielded **zero A/B**, C = PFE, EMR, PCRX, VKTX, and **39 D qualifiers**, of which 25 appear in the bounded chart queue. The five triggered Crash Base names in that queue are WRBY, AMBA, SHOO, DBRG and REGN; non-Crash Bottom names also qualify. These are numeric research admissions only, not owner-approved chart judgments. D can include weak-RS, unfinished or mature secondary structures. Review these and counterexamples across the required five prospective shadow sessions and at least 25 weekly charts before changing any production display or alert mode.

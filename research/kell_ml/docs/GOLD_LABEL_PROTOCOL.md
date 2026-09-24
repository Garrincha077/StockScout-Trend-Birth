# Gold Label Protocol

One Gold case is a frozen ticker + date snapshot.

The structural reviewer may inspect only information available through that date. Forward outcomes stay hidden until the stage/setup label is locked.

## Required fields

case_id
ticker
snapshot_date
primary_stage
setup_status
sequence_evidence
weekly_context
relative_strength_context
volume_context
extension_state
logical_invalidation
reviewer_confidence
source_notes
anti_case_reason

## Primary stage

Use exactly one:
- REVERSAL_EXTENSION
- WEDGE_POP
- EMA_CROSSBACK
- BASE_N_BREAK
- EXHAUSTION_EXTENSION
- WEDGE_DROP
- REPAIR_OR_OTHER

## Hard negatives

Actively include:
- EMA crossover without prior tightening/repair;
- second/third/fourth EMA touch instead of first Crossback;
- high RVOL with no low-risk setup;
- tight base with relative weakness;
- attractive daily chart contradicted by weekly extension;
- gap into late-stage exhaustion;
- late continuation base after multiple extensions.

## Dataset tiers

Gold = human-reviewed and locked.
Silver = deterministic project proxy.
Unlabeled = features/outcomes only.

Never silently promote Silver to Gold.


## Setup status

Use exactly one project review status:

- READY
- NEAR_READY
- LEADER_WAIT
- EXTENDED
- REPAIR
- REJECT

These are StockScout/Work review labels, not terminology published by Oliver Kell. Keep them separate from the primary structural stage.

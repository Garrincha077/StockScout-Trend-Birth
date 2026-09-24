# Milestone v0.1

Status: implemented research baseline; not production.

Implemented:
- point-in-time daily feature engine;
- conservative completed-week weekly context;
- benchmark-relative strength;
- EMA recapture/retest/first-retest sequence proxies;
- transparent Silver stage labels;
- forward returns/MFE/MAE in a separate target layer;
- chronological splits;
- baseline structure classifier;
- baseline opportunity classifier/ranker;
- future-mutation leakage tests;
- Gold-label and proxy documentation.

Test finding during development:
- the first weekly implementation treated a history truncated mid-week as a completed weekly bar;
- the mutation test caught it;
- v0.1 was changed to conservative Friday-close weekly context;
- local test suite passed after the fix.

Not yet solved:
- survivorship-aware US historical universe;
- delisted symbol mapping;
- point-in-time fundamentals;
- exchange-holiday-aware weekly calendar;
- first 100-200 Gold/hard-negative labels;
- pairwise learning-to-rank;
- production integration.

Interpretation guardrail:
a model that reproduces deterministic Silver labels is not evidence that it has learned Oliver Kell. Gold labels and walk-forward validation are required.

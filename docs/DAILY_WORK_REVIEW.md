# Daily Work Review Contract

Status: lab contract for `feature/unified-review-grid-lab`

## Goal

ChatGPT Work reviews the already-selected daily Trend Birth lab candidates. It does **not** modify StockScout Unified, its rankings, its Telegram delivery, or broker state.

The deterministic builder owns:
- candidate sources;
- chart bars;
- EMA10/20;
- 50D / 30W slope;
- RSI14;
- range/base proxy;
- swing HH/HL;
- RVOL;
- Kell Daily Leader qualification.

Work owns only the higher-level review overlay:
- current review state;
- concise interpretation;
- preferred trade style;
- QoQ fundamental direction;
- risk/caveat note.

## Per-ticker output

Write one object keyed by ticker:

```json
{
  "JD": {
    "status": "WATCH",
    "state": "SPRING WATCH",
    "summary": "Price is still rebuilding structure; no need to chase a breakout.",
    "preferredTrade": "Failed breakdown/reclaim starter; add on HL then HH.",
    "fundamentalsQoQ": "Revenue and consolidated profit improving QoQ; watch core retail margin.",
    "riskNote": "30W and 50D are not yet both rising."
  }
}
```

Allowed `status` values for the lab UI:
- `ACTION` — a defined entry pattern is present now;
- `WATCH` — setup is developing and has a concrete next trigger;
- `REVIEW` — interesting discovery, but no defined entry pattern yet;
- `AVOID` — current structure is too extended/damaged for the intended playbook.

## Review principles

1. Do not turn every candidate into a breakout trade.
2. Prefer the entry style appropriate to regime:
   - long Stage 1 / bottoming: spring, failed breakdown, reclaim, new HL;
   - trend transition: pullback to 10/20 EMA or prior HL;
   - Kell first thrust: first controlled pullback / tight pause, not automatic chase;
   - Kell gap-up: do not chase the opening gap; distinguish a held gap from a fade, then prefer tightness, first pullback/reclaim, or next-day continuation with a clear gap-day invalidation;
   - mature/extended move: wait or avoid.
3. Explicitly distinguish current/intact HH+HL from an older historical HH/HL sequence.
4. Treat 3x+ RVOL as attention evidence, not a buy signal.
5. QoQ fundamentals should use the latest reported quarter versus the immediately prior reported quarter. Note seasonality or one-offs when material.
6. Keep fundamental and technical evidence separate; one should not silently override the other.
7. If public evidence is incomplete, say so rather than inventing a value.
8. Analysis is research support; no broker order is created by this workflow.

## Daily prioritization

Work may review every ticker, but the first pass should prioritize:
1. `Multi-hit` names appearing in two or more source modes;
2. strict Kell Daily Leaders;
3. candidates whose deterministic state changed materially since the prior snapshot;
4. Bottom names near spring/reclaim/HL confirmation;
5. Next/Ryan names with a clean pullback rather than extension.

The GridView always remains usable even if Work analysis is absent or stale; the UI falls back to deterministic rule-based review.

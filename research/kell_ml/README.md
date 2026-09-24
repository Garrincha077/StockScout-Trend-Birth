# Kell ML Lab v0.1

Experimental, point-in-time machine-learning research layer for StockScout.

Isolation rule: this directory is research-only. It does not change Unified EOD, Trend Birth publication, candidate generation, ranking, Telegram delivery, or any production workflow.

## Goal

Learn from historical stock snapshots without collapsing Oliver Kell's qualitative framework into one opaque score.

The lab separates:

1. Structure model — what state is the chart in now?
2. Opportunity model — how did comparable point-in-time states perform later?
3. Candidate ranking — sort current candidates by an explicitly defined outcome model.

The key conceptual guardrail remains:

SCREEN != STAGE != SETUP

Silver labels are StockScout project proxies. They are not Kell-published formulas. Human-reviewed Gold labels are the intended ground truth for later versions.

## Input

Daily split-adjusted OHLCV:

ticker,date,open,high,low,close,volume

Optional benchmark:

date,close

QQQ is the preferred benchmark for growth/momentum Kell context.

## Point-in-time controls

- MODEL_FEATURES contains no fwd_*, mfe_*, mae_* or future_* columns.
- Forward outcomes are computed separately and may be targets/evaluation only.
- Weekly context is conservatively updated from Friday closes only in v0.1.
- Chronological train/validation/test splits are used instead of random splits.
- Mutation tests verify that extreme changes in later prices/volume cannot change earlier features.

## Install and test

From research/kell_ml:

    python -m pip install -r requirements.txt
    pytest -q

## Known limitations

- Silver proxy labels are bootstrapping labels, not Gold Kell labels.
- A model fitted to Silver labels has learned the proxy definitions, not Oliver Kell.
- v0.1 does not solve survivorship-aware historical universe construction.
- Delisted symbols and point-in-time fundamentals are not yet ingested.
- Friday-only weekly context is intentionally conservative and does not yet handle exchange-holiday weeks perfectly.
- No production integration is implied.

See docs/KELL_ML_METHOD.md, docs/GOLD_LABEL_PROTOCOL.md, docs/PROXY_REGISTRY.md and docs/DATA_CONTRACT.md.

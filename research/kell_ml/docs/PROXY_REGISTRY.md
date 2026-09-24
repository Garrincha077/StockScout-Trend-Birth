# Kell Project Proxy Registry v0.1

Every number below is a StockScout/Kell overlay research proxy, not a numeric rule published by Oliver Kell.

| Proxy | v0.1 value | Purpose |
|---|---:|---|
| EMA cluster tightness | <= 3.5% | possible recapture/Wedge Pop candidate |
| EMA retest tolerance | +/- 0.35 ATR14 | possible pullback into EMA area |
| Reversal prior decline | 20D <= -10% | bootstrap Reversal Extension cases |
| Reversal volume | RVOL20 >= 1.3 | bootstrap capitulation/attention |
| Base contraction | 20D range / 60D range <= 0.72 | contracting-base candidate |
| Daily exhaustion | distance from EMA10 >= 2.6 ATR | extension candidate |
| Weekly extension context | weekly distance >= 18% plus daily >= 1.8 ATR | multi-timeframe stretch |
| Default opportunity target | +20% at 60D and MAE >= -15% | research target only |

Centralize, test and challenge these values. Do not let them become undocumented "canonical Kell rules".


## Selection context kept separate from stage

Two fields come directly from Kell's stated name-selection preferences and are **not** used to rewrite structural stage:

- kell_price_floor_pass: close >= $10. Kell states he does not trade stocks under $10.
- kell_liquidity_pref_pass: 20D average volume >= 1,000,000 shares. Kell describes roughly 1M shares/day or more as a preference.

review_bucket_proxy is a project classification, not Kell terminology:

- PRIORITY_REVIEW: actionable structural proxy + price/liquidity preference + either positive 20D RS vs benchmark or RVOL20 >= 1.3.
- STRUCTURE_ONLY: actionable structural proxy without enough selection confirmation.
- PRICE_INELIGIBLE: below Kell's stated $10 floor.
- EXTENDED: exhaustion proxy.
- REPAIR: Wedge Drop proxy.
- WATCH: none of the above.

This separation preserves SCREEN != STAGE != SETUP/SELECTION.

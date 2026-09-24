# Historical data sources for Kell ML

The model code is provider-neutral. Raw vendor data and credentials must remain outside the repository.

## Data requirements

For structure learning:
- daily OHLCV;
- enough pre-snapshot history for EMA/ATR/base/RS features;
- benchmark history (QQQ preferred for growth/momentum context);
- broad examples including failures and non-leaders.

For unbiased opportunity/ranking research:
- point-in-time investable universe;
- delisted securities;
- stable security identity across ticker changes where possible;
- split handling that does not leak later corporate actions into historical level filters;
- clear provenance and adjustment method.

## Preferred no-cost research bootstrap: QuantRocket learning bundle

QuantRocket documents a free learning bundle with daily history for all US stocks from 2007 through 2011, including stocks that later delisted. This is an attractive first broad, survivorship-aware corpus because it contains the 2008 bear market and subsequent recovery.

It requires a QuantRocket environment/account and ingestion outside this repository. Export to the provider-neutral contract:

ticker,date,open,high,low,close,volume

Then run:

    python historical_panel_cli.py \
      --prices /path/usstock-learn-2007-2011.csv \
      --benchmark /path/qqq-2007-2011.csv \
      --out-dir artifacts/qr-2007-2011 \
      --max-gold-cases 200

Do not commit the raw licensed dataset.

## Alpha Vantage

Useful capabilities:
- daily equity history;
- listing/delisting status at a historical date from 2010 onward.

This can help reconstruct point-in-time universes, but free-key request limits make full-market price collection slow. Use it for metadata cross-checks or smaller seed studies unless a higher-throughput key is available.

## Existing StockScout Review Grid shards

The current Review Grid contains real recent candidate OHLCV histories. These are useful for:
- integration tests;
- current-candidate regression checks;
- verifying mixed date encodings;
- checking that stage and setup/selection remain separate.

They are **not** an unbiased historical training universe because the symbols were selected by the current scan.

## MarketParquet free recent window

The provider documents a free recent-year daily panel across US stocks with delisted symbols retained. This can provide a recent broad-market sanity dataset, but the free window is too short to be the sole historical training corpus.

## Long-horizon research

A serious multi-cycle opportunity model should eventually use a licensed survivorship-aware provider (for example Sharadar or another source with equivalent delisted/security-master quality). Keep provider adapters separate from Kell feature logic.

## Dataset promotion rule

No dataset is allowed to become the canonical opportunity-model training set until its provenance audit answers:

1. Are delisted names present?
2. Is universe membership point-in-time?
3. How are ticker changes/reuse handled?
4. Are price levels raw or adjusted, and can adjustments leak future information?
5. Are ETFs/funds/non-common securities explicitly identified?
6. Can the exact dataset version be rebuilt or checksummed?

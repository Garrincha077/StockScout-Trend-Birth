from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from kell_ml_v01 import (
    MODEL_FEATURES,
    OPPORTUNITY_FEATURES,
    add_opportunity_target,
    add_review_bucket_proxy,
    apply_silver_labels,
    assert_no_forward_features,
    build_dataset,
    compute_features,
    load_stockscout_chart_shard,
    temporal_split,
    train_opportunity,
)


def bars(seed=7, periods=780, tickers=("AAA", "BBB", "CCC")):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-01", periods=periods)
    rows = []
    for j, ticker in enumerate(tickers):
        rets = rng.normal(0.0004 + j * 0.0001, 0.022 + j * 0.002, len(dates))
        close = (30 + 10 * j) * np.exp(np.cumsum(rets))
        open_ = close * (1 + rng.normal(0, 0.004, len(dates)))
        high = np.maximum(open_, close) * (1 + rng.uniform(0.002, 0.025, len(dates)))
        low = np.minimum(open_, close) * (1 - rng.uniform(0.002, 0.025, len(dates)))
        volume = rng.integers(500_000, 5_000_000, len(dates))
        rows += [
            (ticker, d, o, h, l, c, v)
            for d, o, h, l, c, v in zip(dates, open_, high, low, close, volume)
        ]
    return pd.DataFrame(
        rows, columns=["ticker", "date", "open", "high", "low", "close", "volume"]
    )


def benchmark(periods=780):
    rng = np.random.default_rng(11)
    dates = pd.bdate_range("2021-01-01", periods=periods)
    close = 300 * np.exp(np.cumsum(rng.normal(0.00035, 0.012, len(dates))))
    return pd.DataFrame({"date": dates, "close": close})


def test_no_forward_fields_in_model_contract():
    assert_no_forward_features()
    assert not any(
        c.startswith(("fwd_", "mfe_", "mae_", "future_")) for c in MODEL_FEATURES
    )


def test_future_mutation_cannot_change_past_features():
    raw = bars()
    qqq = benchmark()
    cutoff = pd.Timestamp("2023-03-01")

    early_raw = raw[raw["date"] <= cutoff]
    early_q = qqq[qqq["date"] <= cutoff]
    left = compute_features(early_raw, early_q)

    changed = raw.copy()
    mask = changed["date"] > cutoff
    changed.loc[mask, ["open", "high", "low", "close"]] *= 20
    changed.loc[mask, "volume"] *= 100
    right = compute_features(changed, qqq)
    right = right[right["date"] <= cutoff]

    cols = ["ticker", "date"] + OPPORTUNITY_FEATURES
    assert_frame_equal(
        left[cols].reset_index(drop=True),
        right[cols].reset_index(drop=True),
        check_dtype=False,
        atol=1e-12,
        rtol=1e-12,
    )


def test_monday_cannot_see_friday_weekly_close():
    dates = pd.to_datetime(
        ["2024-01-05", "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12"]
    )
    df = pd.DataFrame(
        {
            "ticker": "AAA",
            "date": dates,
            "open": [10] * 6,
            "high": [11, 11, 11, 11, 11, 101],
            "low": [9] * 6,
            "close": [10, 10, 10, 10, 10, 100],
            "volume": [1000, 1000, 1000, 1000, 1000, 100000],
        }
    )
    early = compute_features(df.iloc[:2])
    full = compute_features(df)
    a = early.loc[early["date"] == pd.Timestamp("2024-01-08"), "weekly_price_vs_ema10_pct"].iloc[0]
    b = full.loc[full["date"] == pd.Timestamp("2024-01-08"), "weekly_price_vs_ema10_pct"].iloc[0]
    assert a == b


def test_first_retest_overrides_base_proxy_in_silver_stage():
    row = {
        "ticker": "AAA",
        "ret_20d": 0.0,
        "rvol_20": 1.0,
        "reversal_bar_proxy": 0,
        "recapture_ema_cluster_proxy": 0,
        "first_retest_after_recapture_proxy": 1,
        "breakout_60d_proxy": 1,
        "range_contraction_20_vs_60": 0.5,
        "dist_ema10_atr": 0.0,
        "weekly_price_vs_ema10_pct": 0.0,
        "ema10_slope_5d": 0.0,
        "ema20_slope_5d": 0.0,
        "price_vs_ema10_pct": 0.0,
        "price_vs_ema20_pct": 0.0,
    }
    out = apply_silver_labels(pd.DataFrame([row]))
    assert out.loc[0, "silver_stage"] == "EMA_CROSSBACK_PROXY"
    assert out.loc[0, "silver_label_source"] == "STOCKSCOUT_KELL_PROJECT_PROXY"


def test_end_to_end_opportunity_model_smoke():
    raw = bars(periods=1000, tickers=("AAA", "BBB", "CCC", "DDD"))
    qqq = benchmark(periods=1000)
    data = build_dataset(raw, qqq)
    data = add_opportunity_target(data, horizon=60, min_return=0.05, max_adverse=-0.30)
    split = temporal_split(data, train_end="2022-06-30", validation_end="2023-06-30")
    train = pd.concat([split.train, split.validation], ignore_index=True)
    target = "opportunity_60d_target"
    if train[target].dropna().nunique() >= 2 and split.test[target].notna().any():
        _, metrics = train_opportunity(train, split.test, target)
        assert "balanced_accuracy" in metrics


def test_stockscout_shard_loader_normalizes_iso_and_unix_seconds():
    payload = {
        "charts": {
            "AAA": {
                "daily": [
                    ["2026-09-21", 10, 11, 9, 10.5, 1_100_000],
                    [1790121600, 10.5, 12, 10, 11.5, 1_200_000],
                ]
            }
        }
    }
    out = load_stockscout_chart_shard(payload)
    assert out["date"].dt.year.tolist() == [2026, 2026]
    assert out["date"].dt.month.tolist() == [9, 9]
    assert out["date"].dt.day.tolist() == [21, 23]


def test_stage_is_not_rewritten_by_setup_quality_or_price_floor():
    base = pd.DataFrame(
        [
            {
                "silver_stage": "EMA_CROSSBACK_PROXY",
                "rs_20d_vs_benchmark": -0.08,
                "rvol_20": 0.7,
                "kell_price_floor_pass": 1,
                "kell_liquidity_pref_pass": 1,
            },
            {
                "silver_stage": "EMA_CROSSBACK_PROXY",
                "rs_20d_vs_benchmark": 0.06,
                "rvol_20": 1.5,
                "kell_price_floor_pass": 0,
                "kell_liquidity_pref_pass": 1,
            },
        ]
    )
    out = add_review_bucket_proxy(base)
    assert out.loc[0, "silver_stage"] == "EMA_CROSSBACK_PROXY"
    assert out.loc[0, "review_bucket_proxy"] == "STRUCTURE_ONLY"
    assert out.loc[1, "silver_stage"] == "EMA_CROSSBACK_PROXY"
    assert out.loc[1, "review_bucket_proxy"] == "PRICE_INELIGIBLE"

from __future__ import annotations

"""Kell ML v0.1 research prototype.

Research-only. No production StockScout/Unified paths import this module.

Core contract:
- features at date t use data <= t only;
- future returns/MFE/MAE are targets/evaluation only;
- Silver labels are StockScout project proxies, not Kell-published formulas;
- chronology is split by date, never randomly.
"""

from dataclasses import dataclass
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline


REQUIRED = ("ticker", "date", "open", "high", "low", "close", "volume")

STRUCTURE_FEATURES = [
    "ret_5d", "ret_20d", "ret_60d", "ret_120d",
    "price_vs_ema10_pct", "price_vs_ema20_pct",
    "price_vs_sma50_pct", "price_vs_sma200_pct",
    "ema10_slope_5d", "ema20_slope_5d", "ema_cluster_width_pct",
    "atr14_pct", "dist_ema10_atr", "dist_ema20_atr",
    "rvol_20", "rvol_50", "volume_dryup_5_vs_20",
    "distance_52w_high_pct", "distance_60d_high_pct",
    "range_20d_pct", "range_60d_pct", "range_contraction_20_vs_60",
    "gap_pct", "true_range_atr",
    "rs_20d_vs_benchmark", "rs_60d_vs_benchmark", "rs_120d_vs_benchmark",
    "benchmark_above_ema20",
    "weekly_price_vs_ema10_pct", "weekly_ema10_slope_4w",
    "recapture_ema_cluster_proxy", "bars_since_recapture_proxy",
    "ema_retest_proxy", "retest_number_since_recapture_proxy",
    "first_retest_after_recapture_proxy",
    "breakout_60d_proxy", "reversal_bar_proxy",
]

NAME_SELECTION_FEATURES = [
    "avg_volume_20",
    "avg_dollar_volume_20",
    "kell_price_floor_pass",
    "kell_liquidity_pref_pass",
]

# Backward-compatible alias: structure classification must not be taught
# name-selection preferences such as price/liquidity.
MODEL_FEATURES = STRUCTURE_FEATURES
OPPORTUNITY_FEATURES = STRUCTURE_FEATURES + NAME_SELECTION_FEATURES


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.replace(0, np.nan)


def _parse_date(value):
    """Parse ISO-like dates and StockScout Unix-second timestamps safely."""
    if isinstance(value, (int, float, np.integer, np.floating)) and not pd.isna(value):
        # StockScout chart shards sometimes serialize dates as Unix seconds.
        if abs(float(value)) >= 10_000_000:
            return pd.to_datetime(value, unit="s", utc=False)
    if isinstance(value, str) and value.isdigit() and len(value) in (10, 13):
        unit = "s" if len(value) == 10 else "ms"
        return pd.to_datetime(int(value), unit=unit, utc=False)
    return pd.to_datetime(value, utc=False)


def _validate(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")
    out = df.copy()
    out["date"] = out["date"].map(_parse_date)
    out = out.sort_values(["ticker", "date"]).reset_index(drop=True)
    if out.duplicated(["ticker", "date"]).any():
        raise ValueError("Duplicate ticker/date rows")
    return out


def load_stockscout_chart_shard(source: dict | str | Path) -> pd.DataFrame:
    """Load the existing Review Grid/Kell chart-shard format into OHLCV rows.

    Expected daily bar layout: [date, open, high, low, close, volume].
    Date may be ISO text or Unix seconds.
    """
    if isinstance(source, (str, Path)):
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
    else:
        payload = source
    charts = payload.get("charts", payload)
    rows = []
    for ticker, chart in charts.items():
        for bar in chart.get("daily", []):
            if len(bar) < 6:
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "date": bar[0],
                    "open": bar[1],
                    "high": bar[2],
                    "low": bar[3],
                    "close": bar[4],
                    "volume": bar[5],
                }
            )
    if not rows:
        raise ValueError("No daily chart rows found in StockScout shard")
    return _validate(pd.DataFrame(rows))


def _weekly_context(g: pd.DataFrame) -> pd.DataFrame:
    """Conservative leak-safe weekly context.

    v0.1 accepts Friday observations only. This avoids treating a history
    truncated on Monday-Thursday as a completed weekly bar. Exchange-calendar
    holiday handling is a known follow-up.
    """
    w = g.loc[g["date"].dt.weekday == 4, ["date", "close"]].copy()
    if w.empty:
        return pd.DataFrame(
            columns=["weekly_date", "weekly_close", "weekly_ema10", "weekly_ema10_slope_4w"]
        )
    w = w.rename(columns={"date": "weekly_date", "close": "weekly_close"})
    w["weekly_ema10"] = w["weekly_close"].ewm(span=10, adjust=False).mean()
    w["weekly_ema10_slope_4w"] = w["weekly_ema10"].pct_change(4)
    return w


def _add_sequence_proxies(g: pd.DataFrame) -> pd.DataFrame:
    g = g.copy()
    top = g[["ema10", "ema20"]].max(axis=1)
    bottom = g[["ema10", "ema20"]].min(axis=1)
    prev_close = g["close"].shift(1)
    prev_top = top.shift(1)

    # Project proxy, not a Kell-published numeric threshold.
    g["recapture_ema_cluster_proxy"] = (
        (g["close"] > top)
        & (prev_close <= prev_top)
        & (g["ema_cluster_width_pct"] <= 0.035)
    ).astype(int)

    tolerance = 0.35 * g["atr14"]  # project proxy
    g["ema_retest_proxy"] = (
        (g["low"] <= top + tolerance)
        & (g["high"] >= bottom - tolerance)
        & (g["close"] >= bottom - tolerance)
    ).astype(int)

    bars_since, retest_num, first = [], [], []
    last_recapture = None
    touches = 0
    for i, row in enumerate(g.itertuples(index=False)):
        if int(getattr(row, "recapture_ema_cluster_proxy")) == 1:
            last_recapture = i
            touches = 0
        if last_recapture is None:
            bars_since.append(np.nan)
            retest_num.append(np.nan)
            first.append(0)
            continue
        distance = i - last_recapture
        bars_since.append(float(distance))
        is_touch = int(getattr(row, "ema_retest_proxy")) == 1 and distance > 0
        if is_touch:
            touches += 1
        retest_num.append(float(touches))
        first.append(int(is_touch and touches == 1))

    g["bars_since_recapture_proxy"] = bars_since
    g["retest_number_since_recapture_proxy"] = retest_num
    g["first_retest_after_recapture_proxy"] = first
    return g


def compute_features(
    ohlcv: pd.DataFrame,
    benchmark: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute point-in-time features only."""
    df = _validate(ohlcv)

    bf = None
    if benchmark is not None:
        b = benchmark.copy()
        b["date"] = pd.to_datetime(b["date"], utc=False)
        b = b.sort_values("date").drop_duplicates("date")
        b["benchmark_ret_20d"] = b["close"].pct_change(20)
        b["benchmark_ret_60d"] = b["close"].pct_change(60)
        b["benchmark_ret_120d"] = b["close"].pct_change(120)
        b["benchmark_ema20"] = b["close"].ewm(span=20, adjust=False).mean()
        b["benchmark_above_ema20"] = (b["close"] > b["benchmark_ema20"]).astype(int)
        bf = b[
            [
                "date", "benchmark_ret_20d", "benchmark_ret_60d",
                "benchmark_ret_120d", "benchmark_above_ema20",
            ]
        ]

    outputs = []
    for _, group in df.groupby("ticker", sort=False):
        g = group.copy().sort_values("date").reset_index(drop=True)
        prev = g["close"].shift(1)
        tr = pd.concat(
            [
                g["high"] - g["low"],
                (g["high"] - prev).abs(),
                (g["low"] - prev).abs(),
            ],
            axis=1,
        ).max(axis=1)
        g["true_range"] = tr
        g["atr14"] = tr.rolling(14, min_periods=5).mean()
        g["atr14_pct"] = _safe_div(g["atr14"], g["close"])

        g["ema10"] = g["close"].ewm(span=10, adjust=False).mean()
        g["ema20"] = g["close"].ewm(span=20, adjust=False).mean()
        g["sma50"] = g["close"].rolling(50, min_periods=20).mean()
        g["sma200"] = g["close"].rolling(200, min_periods=80).mean()
        g["ema10_slope_5d"] = g["ema10"].pct_change(5)
        g["ema20_slope_5d"] = g["ema20"].pct_change(5)
        g["price_vs_ema10_pct"] = _safe_div(g["close"], g["ema10"]) - 1
        g["price_vs_ema20_pct"] = _safe_div(g["close"], g["ema20"]) - 1
        g["price_vs_sma50_pct"] = _safe_div(g["close"], g["sma50"]) - 1
        g["price_vs_sma200_pct"] = _safe_div(g["close"], g["sma200"]) - 1
        g["ema_cluster_width_pct"] = _safe_div((g["ema10"] - g["ema20"]).abs(), g["close"])
        g["dist_ema10_atr"] = _safe_div(g["close"] - g["ema10"], g["atr14"])
        g["dist_ema20_atr"] = _safe_div(g["close"] - g["ema20"], g["atr14"])

        for h in (5, 20, 60, 120):
            g[f"ret_{h}d"] = g["close"].pct_change(h)

        g["avg_volume_20"] = g["volume"].rolling(20, min_periods=5).mean()
        g["avg_dollar_volume_20"] = (g["close"] * g["volume"]).rolling(20, min_periods=5).mean()
        g["rvol_20"] = _safe_div(g["volume"], g["avg_volume_20"])
        g["rvol_50"] = _safe_div(g["volume"], g["volume"].rolling(50, min_periods=10).mean())
        g["volume_dryup_5_vs_20"] = _safe_div(
            g["volume"].rolling(5, min_periods=3).mean(),
            g["volume"].rolling(20, min_periods=5).mean(),
        )

        high_52w = g["high"].rolling(252, min_periods=40).max()
        high_60 = g["high"].rolling(60, min_periods=20).max()
        high_20 = g["high"].rolling(20, min_periods=10).max()
        low_20 = g["low"].rolling(20, min_periods=10).min()
        low_60 = g["low"].rolling(60, min_periods=20).min()
        g["distance_52w_high_pct"] = _safe_div(g["close"], high_52w) - 1
        g["distance_60d_high_pct"] = _safe_div(g["close"], high_60) - 1
        g["range_20d_pct"] = _safe_div(high_20 - low_20, g["close"])
        g["range_60d_pct"] = _safe_div(high_60 - low_60, g["close"])
        g["range_contraction_20_vs_60"] = _safe_div(g["range_20d_pct"], g["range_60d_pct"])
        g["gap_pct"] = _safe_div(g["open"], prev) - 1
        g["true_range_atr"] = _safe_div(g["true_range"], g["atr14"])

        prior_high = g["high"].shift(1).rolling(60, min_periods=20).max()
        g["breakout_60d_proxy"] = (g["close"] > prior_high).astype(int)
        bar_range = (g["high"] - g["low"]).replace(0, np.nan)
        close_location = (g["close"] - g["low"]) / bar_range
        g["reversal_bar_proxy"] = (
            (g["close"] > g["open"])
            & (close_location >= 0.65)
            & (g["true_range_atr"] >= 1.2)
        ).astype(int)

        w = _weekly_context(g)
        g = pd.merge_asof(
            g.sort_values("date"),
            w.sort_values("weekly_date"),
            left_on="date",
            right_on="weekly_date",
            direction="backward",
        )
        g["weekly_price_vs_ema10_pct"] = _safe_div(g["close"], g["weekly_ema10"]) - 1

        if bf is not None:
            g = g.merge(bf, on="date", how="left")
            g["rs_20d_vs_benchmark"] = g["ret_20d"] - g["benchmark_ret_20d"]
            g["rs_60d_vs_benchmark"] = g["ret_60d"] - g["benchmark_ret_60d"]
            g["rs_120d_vs_benchmark"] = g["ret_120d"] - g["benchmark_ret_120d"]
        else:
            g["rs_20d_vs_benchmark"] = np.nan
            g["rs_60d_vs_benchmark"] = np.nan
            g["rs_120d_vs_benchmark"] = np.nan
            g["benchmark_above_ema20"] = np.nan

        # Source-backed Kell name-selection context kept separate from stage.
        # Kell says he does not trade stocks under $10 and prefers roughly
        # 1M shares/day or more; liquidity is a preference, not a stage rule.
        g["kell_price_floor_pass"] = (g["close"] >= 10.0).astype(int)
        g["kell_liquidity_pref_pass"] = (g["avg_volume_20"] >= 1_000_000).astype(int)

        outputs.append(_add_sequence_proxies(g))

    out = pd.concat(outputs, ignore_index=True)
    missing = [c for c in OPPORTUNITY_FEATURES if c not in out.columns]
    if missing:
        raise AssertionError(f"Feature implementation incomplete: {missing}")
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def apply_silver_labels(features: pd.DataFrame) -> pd.DataFrame:
    """Bootstrap project proxies. These are not Kell-published formulas."""
    df = features.copy()
    stage = np.full(len(df), "REPAIR_OR_OTHER", dtype=object)
    strength = np.zeros(len(df), dtype=float)

    reversal = (
        (df["ret_20d"] <= -0.10)
        & (df["reversal_bar_proxy"] == 1)
        & (df["rvol_20"] >= 1.3)
    )
    wedge_pop = (
        (df["recapture_ema_cluster_proxy"] == 1)
        & (df["ret_20d"] <= 0.05)
        & (df["ema20_slope_5d"] <= 0.015)
    )
    crossback = df["first_retest_after_recapture_proxy"] == 1
    base_break = (
        (df["breakout_60d_proxy"] == 1)
        & (df["range_contraction_20_vs_60"] <= 0.72)
        & (df["ema20_slope_5d"] > -0.005)
    )
    exhaustion = (
        (df["dist_ema10_atr"] >= 2.6)
        | ((df["weekly_price_vs_ema10_pct"] >= 0.18) & (df["dist_ema10_atr"] >= 1.8))
    )
    # Important: group this by ticker before use on a multi-ticker table.
    prior_ext = pd.Series(False, index=df.index)
    for _, idx in df.groupby("ticker", sort=False).groups.items():
        e = exhaustion.loc[idx]
        prior_ext.loc[idx] = e.shift(1).rolling(10, min_periods=1).max().fillna(0).astype(bool)
    wedge_drop = (
        prior_ext
        & (df["price_vs_ema10_pct"] < 0)
        & (df["price_vs_ema20_pct"] < 0)
        & (df["ema10_slope_5d"] < 0)
    )

    # Priority describes structural sequence, not attractiveness.
    for mask, label, value in [
        (reversal, "REVERSAL_EXTENSION_PROXY", 0.65),
        (wedge_pop, "WEDGE_POP_PROXY", 0.65),
        (base_break, "BASE_N_BREAK_PROXY", 0.70),
        (exhaustion, "EXHAUSTION_EXTENSION_PROXY", 0.70),
        (wedge_drop, "WEDGE_DROP_PROXY", 0.75),
        (crossback, "EMA_CROSSBACK_PROXY", 0.80),
    ]:
        stage[mask.to_numpy()] = label
        strength[mask.to_numpy()] = value

    df["silver_stage"] = stage
    df["silver_label_source"] = "STOCKSCOUT_KELL_PROJECT_PROXY"
    df["silver_label_strength"] = strength
    return df


def add_review_bucket_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """Keep structural stage separate from Kell-style selection quality.

    This is a transparent project review bucket, not a Kell-published formula.
    A structurally valid Crossback can therefore remain a Crossback while
    being low priority because RS/liquidity/name-selection evidence is weak.
    """
    x = df.copy()
    status = np.full(len(x), "WATCH", dtype=object)
    stage = x["silver_stage"].astype(str)
    actionable = stage.isin(
        ["WEDGE_POP_PROXY", "EMA_CROSSBACK_PROXY", "BASE_N_BREAK_PROXY"]
    )
    confirmation = (
        (x["rs_20d_vs_benchmark"].fillna(-np.inf) > 0)
        | (x["rvol_20"].fillna(0) >= 1.3)
    )
    liquid = x["kell_liquidity_pref_pass"].fillna(0).astype(bool)
    price_ok = x["kell_price_floor_pass"].fillna(0).astype(bool)

    status[actionable.to_numpy()] = "STRUCTURE_ONLY"
    status[(actionable & confirmation & liquid & price_ok).to_numpy()] = "PRIORITY_REVIEW"
    status[(stage == "EXHAUSTION_EXTENSION_PROXY").to_numpy()] = "EXTENDED"
    status[(stage == "WEDGE_DROP_PROXY").to_numpy()] = "REPAIR"
    # Kell's stated under-$10 avoidance is a name-selection constraint, not
    # a reason to rewrite the chart's structural stage.
    status[(~price_ok).to_numpy()] = "PRICE_INELIGIBLE"

    x["review_bucket_proxy"] = status
    return x


def _future_extreme(s: pd.Series, horizon: int, kind: str) -> pd.Series:
    values = s.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    for i in range(len(values)):
        end = min(len(values), i + horizon + 1)
        window = values[i + 1:end]
        if len(window) < horizon:
            continue
        out[i] = np.nanmax(window) if kind == "max" else np.nanmin(window)
    return pd.Series(out, index=s.index)


def compute_outcomes(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Future-dependent targets/evaluation. Never put these into MODEL_FEATURES."""
    df = _validate(ohlcv)
    outputs = []
    for _, g in df.groupby("ticker", sort=False):
        x = g.copy()
        for h in (5, 20, 60, 120, 250):
            x[f"fwd_return_{h}d"] = x["close"].shift(-h) / x["close"] - 1
        for h in (20, 60, 120):
            hi = _future_extreme(x["high"], h, "max")
            lo = _future_extreme(x["low"], h, "min")
            x[f"mfe_{h}d"] = hi / x["close"] - 1
            x[f"mae_{h}d"] = lo / x["close"] - 1
        outputs.append(x)
    full = pd.concat(outputs, ignore_index=True)
    keep = ["ticker", "date"] + [
        c for c in full.columns if c.startswith(("fwd_", "mfe_", "mae_"))
    ]
    return full[keep]


def build_dataset(
    ohlcv: pd.DataFrame,
    benchmark: pd.DataFrame | None = None,
) -> pd.DataFrame:
    features = add_review_bucket_proxy(apply_silver_labels(compute_features(ohlcv, benchmark)))
    outcomes = compute_outcomes(ohlcv)
    return features.merge(outcomes, on=["ticker", "date"], how="left", validate="one_to_one")


@dataclass(frozen=True)
class TemporalSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


def temporal_split(df: pd.DataFrame, train_end: str, validation_end: str) -> TemporalSplit:
    x = df.copy()
    x["date"] = pd.to_datetime(x["date"])
    a, b = pd.Timestamp(train_end), pd.Timestamp(validation_end)
    if b <= a:
        raise ValueError("validation_end must be after train_end")
    split = TemporalSplit(
        train=x[x["date"] <= a].copy(),
        validation=x[(x["date"] > a) & (x["date"] <= b)].copy(),
        test=x[x["date"] > b].copy(),
    )
    if split.train.empty or split.validation.empty or split.test.empty:
        raise ValueError("train/validation/test must all be non-empty")
    return split


def assert_no_forward_features() -> None:
    bad = [c for c in OPPORTUNITY_FEATURES if c.startswith(("fwd_", "mfe_", "mae_", "future_"))]
    if bad:
        raise AssertionError(f"Forward-looking model features: {bad}")


def _model(feature_cols: list[str]) -> Pipeline:
    prep = ColumnTransformer(
        [("numeric", SimpleImputer(strategy="median"), feature_cols)],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    clf = HistGradientBoostingClassifier(
        learning_rate=0.06,
        max_iter=180,
        max_leaf_nodes=15,
        l2_regularization=0.4,
        random_state=42,
    )
    return Pipeline([("prep", prep), ("model", clf)])


def train_structure(train: pd.DataFrame, evaluation: pd.DataFrame):
    if train["silver_stage"].nunique() < 2:
        raise ValueError("Need at least two stage classes")
    if evaluation.empty:
        raise ValueError("No evaluation rows")
    pipe = _model(STRUCTURE_FEATURES)
    pipe.fit(train[STRUCTURE_FEATURES], train["silver_stage"])
    pred = pipe.predict(evaluation[STRUCTURE_FEATURES])
    labels = sorted(set(train["silver_stage"]) | set(evaluation["silver_stage"]))
    metrics = {
        "macro_f1": float(f1_score(evaluation["silver_stage"], pred, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(evaluation["silver_stage"], pred)),
        "labels": labels,
        "confusion_matrix": confusion_matrix(evaluation["silver_stage"], pred, labels=labels).tolist(),
    }
    return pipe, metrics


def add_opportunity_target(
    df: pd.DataFrame,
    horizon: int = 60,
    min_return: float = 0.20,
    max_adverse: float = -0.15,
) -> pd.DataFrame:
    x = df.copy()
    ret, mae = f"fwd_return_{horizon}d", f"mae_{horizon}d"
    valid = x[ret].notna() & x[mae].notna()
    target = pd.Series(np.nan, index=x.index)
    target.loc[valid] = (
        (x.loc[valid, ret] >= min_return) & (x.loc[valid, mae] >= max_adverse)
    ).astype(int)
    x[f"opportunity_{horizon}d_target"] = target
    return x


def train_opportunity(
    train: pd.DataFrame,
    evaluation: pd.DataFrame,
    target_col: str = "opportunity_60d_target",
):
    tr = train.dropna(subset=[target_col])
    ev = evaluation.dropna(subset=[target_col])
    if tr[target_col].nunique() < 2:
        raise ValueError("Need positive and negative opportunity examples")
    if ev.empty:
        raise ValueError(
            "No complete opportunity targets in evaluation; move holdout earlier or provide more future history"
        )
    pipe = _model(OPPORTUNITY_FEATURES)
    pipe.fit(tr[OPPORTUNITY_FEATURES], tr[target_col].astype(int))
    pred = pipe.predict(ev[OPPORTUNITY_FEATURES])
    metrics = {
        "macro_f1": float(f1_score(ev[target_col].astype(int), pred, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(ev[target_col].astype(int), pred)),
        "confusion_matrix": confusion_matrix(ev[target_col].astype(int), pred, labels=[0, 1]).tolist(),
    }
    return pipe, metrics


def rank_candidates(model: Pipeline, candidates: pd.DataFrame) -> pd.DataFrame:
    classes = list(model[-1].classes_)
    if 1 not in classes:
        raise ValueError("Opportunity model has no positive class")
    p = model.predict_proba(candidates)[:, classes.index(1)]
    out = candidates.copy()
    out["ml_opportunity_probability"] = p
    return out.sort_values("ml_opportunity_probability", ascending=False)


def save_model(model: Pipeline, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)

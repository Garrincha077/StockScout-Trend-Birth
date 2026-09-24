from __future__ import annotations

"""Reproducible public historical structure-only seed smoke.

Source is pinned to a Plotly datasets repository commit. This dataset is NOT
treated as a survivorship-clean universe and MUST NOT be used for predictive
opportunity claims. Its purpose is to exercise historical Kell structure/event
mining on real, non-current-scan stock histories.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd

from kell_ml_v01 import (
    add_review_bucket_proxy,
    apply_silver_labels,
    build_blind_gold_queue,
    compute_features,
    generate_historical_events,
    save_model,
    temporal_split,
    train_structure,
)

SOURCE_COMMIT = "0c447c47b757ad74edecab31f0d72f849d2e67c2"
SOURCE_BLOB = "2a1f02e3675ad8bb6f3a8e536e15f601cfe32fbf"
SOURCE_URL = (
    "https://raw.githubusercontent.com/plotly/datasets/"
    f"{SOURCE_COMMIT}/all_stocks_5yr.csv"
)


def main() -> None:
    raw = pd.read_csv(SOURCE_URL)
    required = {"date", "open", "high", "low", "close", "volume", "Name"}
    missing = required - set(raw.columns)
    if missing:
        raise SystemExit(f"Public seed schema changed; missing {sorted(missing)}")

    prices = raw.rename(columns={"Name": "ticker"})[
        ["ticker", "date", "open", "high", "low", "close", "volume"]
    ].copy()

    # Keep PR CI deterministic and bounded while spanning the alphabet/universe.
    # The full downloaded panel is still the source; 160 symbols are selected
    # by stable SHA-256 order, never by future performance.
    symbols = sorted(
        prices["ticker"].dropna().astype(str).unique(),
        key=lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest(),
    )
    seed_symbols = set(symbols[:160])
    prices = prices[prices["ticker"].astype(str).isin(seed_symbols)].copy()

    # No benchmark and no raw/as-traded-price assertion: structure-only seed.
    features = compute_features(prices, benchmark=None)
    labeled = add_review_bucket_proxy(apply_silver_labels(features))
    events = generate_historical_events(labeled)
    queue = build_blind_gold_queue(events, max_cases=200, max_per_reason_year=12)

    # Actual ML training smoke: chronological Silver-label classifier.
    # Because Silver labels are deterministic proxies derived from these same
    # features, the score measures pipeline reproducibility, NOT Kell skill.
    split = temporal_split(
        labeled,
        train_end="2015-12-31",
        validation_end="2016-12-31",
    )
    _, validation_metrics = train_structure(split.train, split.validation)
    train_through_validation = pd.concat(
        [split.train, split.validation], ignore_index=True
    )
    silver_model, test_metrics = train_structure(
        train_through_validation, split.test
    )

    if prices["ticker"].nunique() != 160:
        raise SystemExit("Unexpected public seed symbol count")
    if len(events) < 1_000:
        raise SystemExit("Unexpectedly few historical event candidates")
    if len(queue) < 100:
        raise SystemExit("Unexpectedly small blind Gold queue")

    out = Path("artifacts/public-structure-seed")
    out.mkdir(parents=True, exist_ok=True)
    queue.to_csv(out / "blind_gold_queue.csv", index=False)
    save_model(silver_model, out / "silver_structure_model.joblib")

    report = {
        "purpose": "historical structure-only seed; not opportunity validation",
        "source_repository": "plotly/datasets",
        "source_commit": SOURCE_COMMIT,
        "source_blob": SOURCE_BLOB,
        "survivorship_clean": False,
        "benchmark_used": False,
        "price_rows": int(len(prices)),
        "symbols": int(prices["ticker"].nunique()),
        "symbol_sampling": "first 160 by SHA256(ticker) stable order; not outcome-selected",
        "first_date": str(pd.to_datetime(prices["date"]).min().date()),
        "last_date": str(pd.to_datetime(prices["date"]).max().date()),
        "event_rows": int(len(events)),
        "blind_gold_queue_rows": int(len(queue)),
        "blind_gold_queue_reason_counts": {
            str(k): int(v)
            for k, v in queue["event_reason"].value_counts().sort_index().items()
        },
        "blind_gold_queue_year_counts": {
            str(k): int(v)
            for k, v in pd.to_datetime(queue["date"]).dt.year.value_counts().sort_index().items()
        },
        "silver_structure_training": {
            "interpretation": (
                "pipeline smoke only; Silver targets are deterministic project "
                "proxies derived from overlapping features"
            ),
            "train_rows": int(len(split.train)),
            "validation_rows": int(len(split.validation)),
            "test_rows": int(len(split.test)),
            "validation_metrics": validation_metrics,
            "test_metrics": test_metrics,
        },
        "event_reason_counts": {
            str(k): int(v)
            for k, v in events["event_reason"].value_counts().sort_index().items()
        },
        "silver_stage_counts": {
            str(k): int(v)
            for k, v in labeled["silver_stage"].value_counts().sort_index().items()
        },
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

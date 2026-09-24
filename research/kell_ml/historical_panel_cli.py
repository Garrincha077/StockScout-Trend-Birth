from __future__ import annotations

"""Build Kell historical research artifacts from a generic OHLCV panel.

This CLI intentionally accepts a provider-neutral CSV so raw vendor data and
credentials stay outside the repository.

Required price columns:
ticker,date,open,high,low,close,volume

Optional benchmark columns:
date,close
"""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from kell_ml_v01 import (
    add_review_bucket_proxy,
    apply_silver_labels,
    build_blind_gold_queue,
    compute_features,
    compute_outcomes,
    generate_historical_events,
    mine_retrospective_structure_cases,
)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--prices", required=True, type=Path)
    p.add_argument("--benchmark", type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--max-gold-cases", type=int, default=200)
    p.add_argument("--with-outcomes", action="store_true")
    p.add_argument("--write-features", action="store_true")
    args = p.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    prices = pd.read_csv(args.prices)
    benchmark = pd.read_csv(args.benchmark) if args.benchmark else None

    features = compute_features(prices, benchmark)
    features = add_review_bucket_proxy(apply_silver_labels(features))
    events = generate_historical_events(features)
    queue = build_blind_gold_queue(events, max_cases=args.max_gold_cases)

    events.to_csv(out / "historical_events.csv", index=False)
    queue.to_csv(out / "blind_gold_queue.csv", index=False)
    if args.write_features:
        features.to_csv(out / "point_in_time_features.csv", index=False)

    manifest = {
        "prices_file": str(args.prices),
        "prices_sha256": file_sha256(args.prices),
        "benchmark_file": str(args.benchmark) if args.benchmark else None,
        "benchmark_sha256": file_sha256(args.benchmark) if args.benchmark else None,
        "price_rows": int(len(prices)),
        "symbols": int(prices["ticker"].nunique()),
        "first_date": str(pd.to_datetime(prices["date"]).min().date()),
        "last_date": str(pd.to_datetime(prices["date"]).max().date()),
        "feature_rows": int(len(features)),
        "event_rows": int(len(events)),
        "gold_queue_rows": int(len(queue)),
        "contains_forward_outcomes": bool(args.with_outcomes),
    }

    if args.with_outcomes:
        outcomes = compute_outcomes(prices)
        dataset = features.merge(
            outcomes, on=["ticker", "date"], how="left", validate="one_to_one"
        )
        retrospective = mine_retrospective_structure_cases(dataset)
        retrospective.to_csv(out / "retrospective_structure_cases.csv", index=False)
        manifest["retrospective_case_rows"] = int(len(retrospective))

    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

from __future__ import annotations

"""Blind historical chart packets for Kell structure labeling.

Every chart is truncated at snapshot_date. No future returns, future bars,
outcomes, or opportunity labels are shown.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd


def extract_blind_window(
    prices: pd.DataFrame,
    ticker: str,
    snapshot_date,
    daily_lookback: int = 160,
) -> pd.DataFrame:
    x = prices.copy()
    x["date"] = pd.to_datetime(x["date"])
    snap = pd.Timestamp(snapshot_date)
    w = (
        x[(x["ticker"].astype(str) == str(ticker)) & (x["date"] <= snap)]
        .sort_values("date")
        .tail(daily_lookback)
        .copy()
    )
    if w.empty:
        raise ValueError(f"No blind price window for {ticker} @ {snap.date()}")
    if w["date"].max() > snap:
        raise AssertionError("Future bar leaked into blind chart window")
    return w


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def _weekly_completed(daily: pd.DataFrame) -> pd.DataFrame:
    # Conservative v0.1 rule: only Friday closes become weekly observations.
    w = daily[daily["date"].dt.weekday == 4][["date", "close"]].copy()
    if w.empty:
        return w
    w["ema10"] = _ema(w["close"], 10)
    return w.tail(45)


def render_case_png(
    daily: pd.DataFrame,
    case_id: str,
    ticker: str,
    snapshot_date,
    event_reason: str,
    out_path: str | Path,
) -> None:
    d = daily.copy().reset_index(drop=True)
    d["ema10"] = _ema(d["close"], 10)
    d["ema20"] = _ema(d["close"], 20)
    d["sma50"] = d["close"].rolling(50, min_periods=20).mean()
    weekly = _weekly_completed(d)

    fig = plt.figure(figsize=(12, 8))
    gs = fig.add_gridspec(3, 1, height_ratios=[4.5, 1.2, 2.2], hspace=0.08)
    ax = fig.add_subplot(gs[0])
    av = fig.add_subplot(gs[1], sharex=ax)
    aw = fig.add_subplot(gs[2])

    xs = np.arange(len(d))
    width = 0.58
    for i, row in d.iterrows():
        up = row["close"] >= row["open"]
        color = "tab:blue" if up else "tab:orange"
        ax.vlines(i, row["low"], row["high"], linewidth=0.7, color=color)
        bottom = min(row["open"], row["close"])
        height = abs(row["close"] - row["open"])
        if height == 0:
            height = max((row["high"] - row["low"]) * 0.02, 1e-6)
        ax.add_patch(
            Rectangle(
                (i - width / 2, bottom),
                width,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.4,
            )
        )

    ax.plot(xs, d["ema10"], linewidth=1.0, label="EMA10")
    ax.plot(xs, d["ema20"], linewidth=1.0, label="EMA20")
    ax.plot(xs, d["sma50"], linewidth=0.9, label="SMA50")
    ax.legend(loc="upper left", fontsize=8, ncol=3)
    ax.grid(alpha=0.15)
    ax.tick_params(axis="x", labelbottom=False)
    ax.set_title(
        f"{case_id} | {ticker} | snapshot {pd.Timestamp(snapshot_date).date()} | "
        f"{event_reason} | BLIND: no bars after snapshot",
        fontsize=10,
    )

    av.bar(xs, d["volume"], width=0.8)
    av.set_ylabel("Volume", fontsize=8)
    av.grid(alpha=0.1)
    tick_idx = np.linspace(0, len(d) - 1, min(8, len(d)), dtype=int)
    av.set_xticks(tick_idx)
    av.set_xticklabels(
        [d.iloc[i]["date"].strftime("%Y-%m-%d") for i in tick_idx],
        rotation=30,
        ha="right",
        fontsize=7,
    )

    if not weekly.empty:
        wx = np.arange(len(weekly))
        aw.plot(wx, weekly["close"], linewidth=1.2, label="Weekly close")
        aw.plot(wx, weekly["ema10"], linewidth=1.0, label="Weekly EMA10")
        aw.legend(loc="upper left", fontsize=8, ncol=2)
        wt = np.linspace(0, len(weekly) - 1, min(6, len(weekly)), dtype=int)
        aw.set_xticks(wt)
        aw.set_xticklabels(
            [weekly.iloc[i]["date"].strftime("%Y-%m-%d") for i in wt],
            rotation=30,
            ha="right",
            fontsize=7,
        )
    aw.set_title("Completed-Friday weekly context", fontsize=9)
    aw.grid(alpha=0.15)

    fig.suptitle(
        "Kell historical structure labeling packet — future outcomes hidden",
        fontsize=11,
        y=0.995,
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def build_chart_packets(
    prices: pd.DataFrame,
    queue: pd.DataFrame,
    out_dir: str | Path,
    daily_lookback: int = 160,
    limit: int | None = None,
) -> pd.DataFrame:
    out_dir = Path(out_dir)
    chart_dir = out_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    q = queue.copy()
    if limit is not None:
        q = q.head(limit)

    manifest = []
    for row in q.itertuples(index=False):
        case_id = str(row.case_id)
        ticker = str(row.ticker)
        snap = pd.Timestamp(row.date)
        reason = str(row.event_reason)
        daily = extract_blind_window(
            prices, ticker=ticker, snapshot_date=snap, daily_lookback=daily_lookback
        )
        name = f"{case_id}.png"
        render_case_png(
            daily=daily,
            case_id=case_id,
            ticker=ticker,
            snapshot_date=snap,
            event_reason=reason,
            out_path=chart_dir / name,
        )
        manifest.append(
            {
                "case_id": case_id,
                "ticker": ticker,
                "snapshot_date": snap.strftime("%Y-%m-%d"),
                "event_reason": reason,
                "chart_path": f"charts/{name}",
                "daily_first_bar": daily["date"].min().strftime("%Y-%m-%d"),
                "daily_last_bar": daily["date"].max().strftime("%Y-%m-%d"),
                "daily_bar_count": int(len(daily)),
                "future_bars_included": False,
            }
        )

    out = pd.DataFrame(manifest)
    out.to_csv(out_dir / "chart_manifest.csv", index=False)
    (out_dir / "chart_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return out

# Oliver Kell Overlay Scoring v1

Branch scope: \`feature/kell-mcp-lab\`

This layer scores **only candidates StockScout has already selected**. It does not create a new market-wide universe and does not change candidate membership, source ranks, or the default GridView ordering.

## Data source

The score uses each candidate's existing daily OHLCV \`chartBars\` already carried into the Trend Birth review snapshot. Those bars come from the existing StockScout/Unified provider chain. The current Unified provider configuration uses yfinance as primary with Alpaca as secondary validation/fallback; this branch does not alter that provider chain.

SPY is requested only as an optional benchmark series for \`Strength on Down Day\`. Loading SPY does not add SPY or any other symbol to the candidate universe. If benchmark bars are unavailable, that criterion is marked unavailable and excluded from the score denominator.

## Transparent criteria and weights

The final \`kell_score\` is normalized to 0–100 over the criteria that have enough data.

| Criterion | Weight | v1 proxy |
| --- | ---: | --- |
| 52W / New High | 8 | Close within 3% of 52-week high or current bar makes a new 52-week high |
| Unusual Volume | 10 | Latest volume / prior 20-session average >= 2.0x |
| Bull Snort | 12 | 1D return >= 4%, RVOL20 >= 2.0x, close in top 30% of daily range |
| Doubler / 3M–6M momentum | 8 | 3M return >= 50% or 6M return >= 100% |
| Gapper | 8 | Open >= 3% above prior close |
| Strength on Down Day | 8 | SPY < 0%, stock >= 0%, stock beats SPY by >= 1.5pp, close location >= 60% |
| EMA10 / EMA20 readiness | 10 | Close >= EMA10 >= EMA20, both constructive over 5 sessions, <= 8% above EMA10 |
| Wedge Pop proxy | 10 | Prior 10D range <= 70% of prior 20D range, then close > prior 10D high on RVOL20 >= 1.5x and strong close |
| EMA Crossback proxy | 8 | Stock was at/below EMA10/20 within prior 5 sessions, now closes above both with near-bullish stack |
| Base n' Break proxy | 8 | Prior 20D range <= 18%, prior 40D range <= 30%, close breaks prior 20D high on RVOL20 >= 1.3x |
| Tightening / contraction | 5 | Recent 10D median true-range <= 75% of prior 20D median, or 10D range <= 55% of 40D range |
| Breakout proximity | 5 | Close is between -3.0% and +1.5% of the prior 20D high |

## JSON contract

Each candidate receives:

- \`kell_52w_high\`
- \`kell_unusual_volume\`
- \`kell_bull_snort\`
- \`kell_doubler\`
- \`kell_gapper\`
- \`kell_strength_on_down_day\`
- \`kell_ema_readiness\`
- \`kell_wedge_pop\`
- \`kell_ema_crossback\`
- \`kell_base_n_break\`
- \`kell_tightening\`
- \`kell_breakout_proximity\`
- \`kell_breakout_proximity_pct\`
- \`kell_score\`
- \`score_breakdown\`
- \`kell_metrics\`

\`score_breakdown\` contains the hit state, awarded points, maximum points, availability and a human-readable detail string for every criterion.

These are explicit research proxies, not claims that the formulas reproduce any proprietary Oliver Kell screen exactly.

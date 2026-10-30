"""Bounded chart-only degradation; source and price validation remain separate."""

MINIMUM_CHART_COVERAGE_PCT = 99


def chart_coverage(expected: set[str], available: set[str]) -> dict:
    if available - expected:
        raise ValueError("Kell chart archive contains unexpected tickers")
    missing = sorted(expected - available)
    total = len(expected)
    # Compare integers: rounding must never turn sub-threshold coverage into a pass.
    if total and len(available) * 100 < total * MINIMUM_CHART_COVERAGE_PCT:
        raise ValueError(
            f"Kell chart coverage below {MINIMUM_CHART_COVERAGE_PCT}%: "
            f"{len(available)}/{total}; missing: {', '.join(missing)}"
        )
    return {
        "minimumCoveragePct": MINIMUM_CHART_COVERAGE_PCT,
        "chartCoveragePct": round(100 * len(available) / total, 4) if total else 100.0,
        "missingChartCount": len(missing),
        "missingChartTickers": missing,
        "coverageStatus": "partial" if missing else "complete",
    }

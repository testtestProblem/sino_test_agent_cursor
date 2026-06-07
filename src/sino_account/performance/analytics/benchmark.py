"""Benchmark return calculations."""

from __future__ import annotations

from typing import Any

from sino_account.performance.analytics.kbars_utils import (
    close_on_or_after,
    close_on_or_before,
    kbars_to_series,
)


def calc_benchmark_return_pct(
    benchmark_kbars: dict[str, Any],
    start: str,
    end: str,
) -> float | None:
    series = kbars_to_series(benchmark_kbars)
    if not series:
        return None

    start_close = close_on_or_after(series, start)
    end_close = close_on_or_before(series, end)
    if start_close is None:
        start_close = series[0][1]
    if end_close is None:
        end_close = series[-1][1]

    if start_close <= 0:
        return None

    return (end_close - start_close) / start_close * 100

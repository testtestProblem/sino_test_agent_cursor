"""Aggregate kbars into per-day closing prices."""

from __future__ import annotations

from typing import Any

from sino_account.performance.analytics.kbars_utils import kbars_to_series
from sino_account.performance.date_range import iter_dates


def kbars_to_daily_closes(kbars: dict[str, Any]) -> dict[str, float]:
    """Map calendar date to the last close of that day (minute bars collapse to daily)."""
    daily: dict[str, float] = {}
    for day, close in kbars_to_series(kbars):
        daily[day] = close
    return daily


def forward_fill_daily_closes(
    daily_closes: dict[str, float],
    start: str,
    end: str,
) -> dict[str, float]:
    """Fill missing calendar days with the most recent known close."""
    filled: dict[str, float] = {}
    last_close: float | None = None

    for day in iter_dates(start, end):
        if day in daily_closes:
            last_close = daily_closes[day]
        if last_close is not None:
            filled[day] = last_close

    return filled


def get_close_on_day(
    daily_closes: dict[str, float],
    day: str,
) -> float | None:
    return daily_closes.get(day)


def build_daily_close_map(
    kbars_by_code: dict[str, dict[str, Any]],
    start: str,
    end: str,
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Build forward-filled daily close maps for each stock code."""
    close_map: dict[str, dict[str, float]] = {}
    warnings: list[str] = []

    for code, kbars in sorted(kbars_by_code.items()):
        raw = kbars_to_daily_closes(kbars)
        if not raw:
            warnings.append(f"kbars 無收盤價: {code}")
            continue

        filled = forward_fill_daily_closes(raw, start, end)
        if not filled:
            warnings.append(f"區間內無可用收盤價: {code}")
            continue

        close_map[code] = filled

    return close_map, warnings

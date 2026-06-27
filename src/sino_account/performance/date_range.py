"""Date range helpers."""

from __future__ import annotations

import bisect
from datetime import date, timedelta

# Taiwan listed stocks: cash settlement is T+2 trading sessions after trade date.
STOCK_SETTLEMENT_LAG = 2


def iter_dates(start: str, end: str):
    """Yield inclusive calendar dates from start to end as YYYY-MM-DD strings."""
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if start_date > end_date:
        raise ValueError(f"start date {start} must be on or before end date {end}")

    current = start_date
    while current <= end_date:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def build_weekday_calendar(start: str, end: str) -> list[str]:
    """Fallback trading calendar: Mon–Fri only (no TWSE holidays)."""
    days: list[str] = []
    for day in iter_dates(start, end):
        if date.fromisoformat(day).weekday() < 5:
            days.append(day)
    return days


def settlement_date(
    trade_date: str,
    trading_days: list[str],
    lag: int = STOCK_SETTLEMENT_LAG,
) -> str:
    """Return T+lag settlement date (lag trading sessions after trade_date)."""
    if not trading_days or lag <= 0:
        return trade_date

    idx = bisect.bisect_left(trading_days, trade_date)
    if idx >= len(trading_days):
        idx = len(trading_days) - 1
    elif trading_days[idx] != trade_date:
        if idx == 0:
            trade_idx = 0
        else:
            trade_idx = idx - 1 if trading_days[idx] > trade_date else idx
    else:
        trade_idx = idx

    settle_idx = trade_idx + lag
    if settle_idx < len(trading_days):
        return trading_days[settle_idx]

    last = date.fromisoformat(trading_days[-1])
    remaining = settle_idx - len(trading_days) + 1
    cursor = last
    added = 0
    while added < remaining:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            added += 1
    return cursor.isoformat()

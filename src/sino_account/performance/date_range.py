"""Date range helpers."""

from __future__ import annotations

from datetime import date, timedelta


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

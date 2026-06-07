"""Date range utilities for 3-month performance queries."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta


def three_month_range(end: date | str | None = None) -> tuple[str, str]:
    if end is None:
        end_date = date.today()
    elif isinstance(end, str):
        end_date = date.fromisoformat(end)
    else:
        end_date = end

    month = end_date.month - 3
    year = end_date.year
    while month <= 0:
        month += 12
        year -= 1

    max_day = monthrange(year, month)[1]
    start_date = date(year, month, min(end_date.day, max_day))
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def monthly_chunks(start: str, end: str) -> list[tuple[str, str]]:
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if start_date > end_date:
        raise ValueError(f"start date {start} must be on or before end date {end}")

    chunks: list[tuple[str, str]] = []
    current = start_date
    while current <= end_date:
        if current.month == 12:
            month_end = date(current.year, 12, 31)
        else:
            month_end = date(current.year, current.month + 1, 1) - timedelta(days=1)

        chunk_end = min(month_end, end_date)
        chunks.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        current = chunk_end + timedelta(days=1)

    return chunks

"""Helpers to extract close prices from serialized kbars."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _normalize_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e14:
            ts /= 1e9
        elif ts > 1e11:
            ts /= 1e3
        return datetime.fromtimestamp(ts).date().isoformat()
    text = str(value)
    if "T" in text:
        return text.split("T", 1)[0]
    if " " in text:
        return text.split(" ", 1)[0]
    return text[:10] if len(text) >= 10 else text


def kbars_to_series(kbars: dict[str, Any]) -> list[tuple[str, float]]:
    closes = kbars.get("Close") or kbars.get("close") or []
    timestamps = kbars.get("datetime") or kbars.get("ts") or kbars.get("Date") or []

    if not closes:
        return []

    series: list[tuple[str, float]] = []
    if timestamps and len(timestamps) == len(closes):
        for ts, close in zip(timestamps, closes):
            day = _normalize_date(ts)
            if day is not None:
                series.append((day, float(close)))
    else:
        for index, close in enumerate(closes):
            series.append((str(index), float(close)))

    series.sort(key=lambda item: item[0])
    return series


def close_on_or_after(series: list[tuple[str, float]], target: str) -> float | None:
    for day, close in series:
        if day >= target:
            return close
    return series[-1][1] if series else None


def close_on_or_before(series: list[tuple[str, float]], target: str) -> float | None:
    selected: float | None = None
    for day, close in series:
        if day <= target:
            selected = close
        else:
            break
    return selected

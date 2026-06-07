"""Cash flow approximation from settlements."""

from __future__ import annotations

from typing import Any


def calc_net_cash_flow(settlements: list[dict[str, Any]], start: str, end: str) -> float:
    total = 0.0
    for item in settlements:
        day = str(item.get("date") or "")
        if len(day) >= 10:
            day = day[:10]
        if start <= day <= end:
            total += float(item.get("amount") or 0)
    return total

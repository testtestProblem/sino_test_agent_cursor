"""Realized P&L calculations."""

from __future__ import annotations

from typing import Any


def calc_realized_pnl_total(trades: list[dict[str, Any]]) -> float:
    return sum(float(trade.get("pnl") or 0) for trade in trades)

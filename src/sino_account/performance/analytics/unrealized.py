"""Unrealized P&L and snapshot metrics."""

from __future__ import annotations

from typing import Any

# list_positions() 預設以「張」回報數量，1 張 = 1000 股
STOCK_SHARES_PER_LOT = 1000


def calc_unrealized_pnl_total(positions: list[dict[str, Any]]) -> float:
    return sum(float(position.get("pnl") or 0) for position in positions)


def calc_cash_balance(balance: dict[str, Any]) -> float:
    return float(balance.get("acc_balance") or 0)


def _position_share_multiplier(position: dict[str, Any]) -> float:
    """Return shares per quantity unit (1000 for whole-lot positions)."""
    unit = position.get("unit")
    if unit is not None:
        unit_value = str(unit).lower()
        if unit_value in {"share", "shares"}:
            return 1.0
    return STOCK_SHARES_PER_LOT


def calc_position_market_value(positions: list[dict[str, Any]]) -> float:
    total = 0.0
    for position in positions:
        quantity = float(position.get("quantity") or 0)
        if quantity <= 0:
            continue

        last_price = float(position.get("last_price") or 0)
        price = float(position.get("price") or 0)
        pnl = float(position.get("pnl") or 0)
        multiplier = _position_share_multiplier(position)

        if last_price > 0:
            total += last_price * quantity * multiplier
        elif price > 0:
            total += price * quantity * multiplier + pnl
    return total


def calc_ending_nav(cash_balance: float, position_market_value: float) -> float:
    return cash_balance + position_market_value

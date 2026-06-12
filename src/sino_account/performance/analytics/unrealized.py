"""Unrealized P&L and snapshot metrics."""

from __future__ import annotations

from typing import Any

from sino_account.performance.analytics.quantity_units import (
    STOCK_SHARES_PER_LOT,
    build_code_multipliers,
    calc_positions_market_value,
)


def calc_unrealized_pnl_total(positions: list[dict[str, Any]]) -> float:
    return sum(float(position.get("pnl") or 0) for position in positions)


def calc_cash_balance(balance: dict[str, Any]) -> float:
    return float(balance.get("acc_balance") or 0)


def calc_position_market_value(
    positions: list[dict[str, Any]],
    *,
    multipliers: dict[str, float] | None = None,
    code_units: dict[str, float] | None = None,
) -> float:
    if multipliers is None:
        multipliers = build_code_multipliers(positions, [], code_units=code_units)
    total, _ = calc_positions_market_value(positions, multipliers)
    return total


def calc_position_market_value_with_warnings(
    positions: list[dict[str, Any]],
    *,
    multipliers: dict[str, float] | None = None,
    code_units: dict[str, float] | None = None,
) -> tuple[float, list[str]]:
    if multipliers is None:
        multipliers = build_code_multipliers(positions, [], code_units=code_units)
    return calc_positions_market_value(positions, multipliers)


def calc_ending_nav(cash_balance: float, position_market_value: float) -> float:
    return cash_balance + position_market_value

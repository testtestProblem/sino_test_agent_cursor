"""Portfolio return estimation."""

from __future__ import annotations


def calc_estimated_beginning_nav(
    ending_nav: float,
    realized_pnl_total: float,
    unrealized_pnl_total: float,
    net_cash_flow: float,
) -> float | None:
    value = ending_nav - realized_pnl_total - unrealized_pnl_total + net_cash_flow
    if value <= 0:
        return None
    return value


def calc_portfolio_return_pct(
    ending_nav: float,
    estimated_beginning_nav: float | None,
    net_cash_flow: float,
) -> float | None:
    if estimated_beginning_nav is None or estimated_beginning_nav <= 0:
        return None
    return (
        (ending_nav - estimated_beginning_nav - net_cash_flow) / estimated_beginning_nav * 100
    )


def calc_excess_return_pct(
    portfolio_return_pct: float | None,
    benchmark_return_pct: float | None,
) -> float | None:
    if portfolio_return_pct is None or benchmark_return_pct is None:
        return None
    return portfolio_return_pct - benchmark_return_pct

"""Reconstruct daily holdings by replaying closed trades backward from snapshot."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sino_account.performance.analytics.quantity_units import (
    build_code_multipliers,
    combine_unit_shares,
    position_to_shares,
    trade_undo_shares,
    _is_share_unit,
)
from sino_account.performance.date_range import iter_dates


def _normalize_trade_date(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else text


def _positions_to_shares(
    positions: list[dict[str, Any]],
    multipliers: dict[str, float],
) -> dict[str, float]:
    groups: dict[str, dict[str, float]] = defaultdict(
        lambda: {"common": 0.0, "share": 0.0}
    )
    for position in positions:
        code = str(position.get("code") or "")
        shares = position_to_shares(position, multipliers)
        if not code or shares <= 0:
            continue
        bucket = "share" if _is_share_unit(position) else "common"
        groups[code][bucket] += shares

    holdings: dict[str, float] = {}
    for code, parts in groups.items():
        total = combine_unit_shares(parts["common"], parts["share"])
        if total > 0:
            holdings[code] = total
    return holdings


def build_holdings_timeline(
    trades: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    start: str,
    end: str,
    *,
    code_units: dict[str, float] | None = None,
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Return daily share holdings per code and replay warnings."""
    warnings: list[str] = []
    multipliers = build_code_multipliers(positions, trades, code_units=code_units)
    end_holdings = _positions_to_shares(positions, multipliers)
    trades_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for trade in trades:
        trade_date = _normalize_trade_date(trade.get("date"))
        if not trade_date or trade_date < start or trade_date > end:
            continue
        trades_by_date[trade_date].append(trade)

    trade_dates = sorted(trades_by_date)
    snapshots: dict[str, dict[str, float]] = {}
    current = dict(end_holdings)

    for trade_date in sorted(trades_by_date.keys(), reverse=True):
        snapshots[trade_date] = dict(current)
        for trade in trades_by_date[trade_date]:
            code = str(trade.get("code") or "")
            if not code:
                continue
            undo_shares = trade_undo_shares(trade, multipliers)
            if undo_shares <= 0:
                if float(trade.get("pnl") or 0) != 0:
                    warnings.append(
                        f"無法回放零股平倉張數，持倉可能略有不準: {code} @ {trade_date}"
                    )
                continue
            current[code] = current.get(code, 0.0) + undo_shares

    start_holdings = dict(current)
    timeline: dict[str, dict[str, float]] = {}

    for day in iter_dates(start, end):
        if not trade_dates:
            timeline[day] = dict(end_holdings)
            continue

        if day < trade_dates[0]:
            timeline[day] = dict(start_holdings)
            continue

        if day > trade_dates[-1]:
            timeline[day] = dict(end_holdings)
            continue

        applicable = [trade_date for trade_date in trade_dates if trade_date <= day]
        timeline[day] = dict(snapshots[applicable[-1]])

    return timeline, warnings

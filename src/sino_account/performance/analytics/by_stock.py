"""Per-stock contribution aggregation."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sino_account.performance.models import StockContribution


def _summary_items(summary: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(summary, list):
        return summary
    if isinstance(summary, dict):
        items = summary.get("profitloss_summary")
        if isinstance(items, list):
            return items
    return []


def build_by_stock(
    trades: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    summary: dict[str, Any] | list[Any],
) -> list[StockContribution]:
    trade_counts = Counter(str(trade.get("code") or "") for trade in trades)
    trade_counts.pop("", None)

    realized_by_code: dict[str, float] = {}
    pr_ratio_by_code: dict[str, float | None] = {}
    for item in _summary_items(summary):
        code = str(item.get("code") or "")
        if not code:
            continue
        realized_by_code[code] = float(item.get("pnl") or 0)
        pr_ratio = item.get("pr_ratio")
        pr_ratio_by_code[code] = float(pr_ratio) if pr_ratio is not None else None

    unrealized_by_code: dict[str, float] = {}
    for position in positions:
        code = str(position.get("code") or "")
        if not code:
            continue
        unrealized_by_code[code] = float(position.get("pnl") or 0)

    codes = sorted(set(realized_by_code) | set(unrealized_by_code) | set(trade_counts))
    contributions: list[StockContribution] = []
    for code in codes:
        realized = realized_by_code.get(code, 0.0)
        unrealized = unrealized_by_code.get(code, 0.0)
        contributions.append(
            StockContribution(
                code=code,
                realized_pnl=realized,
                unrealized_pnl=unrealized,
                total_pnl=realized + unrealized,
                trade_count=trade_counts.get(code, 0),
                pr_ratio=pr_ratio_by_code.get(code),
            )
        )

    contributions.sort(key=lambda item: item.total_pnl, reverse=True)
    return contributions

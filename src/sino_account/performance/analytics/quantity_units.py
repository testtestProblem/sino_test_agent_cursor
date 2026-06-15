"""Convert position/trade quantities to share counts (supports whole lots and odd lots)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

STOCK_SHARES_PER_LOT = 1000





def resolve_share_multiplier(record: dict[str, Any]) -> float:

    """Return shares per quantity unit: 1000 for lots, 1 for share-mode records."""

    unit = record.get("unit")

    if unit is not None:

        unit_value = str(unit).lower()

        if unit_value in {"share", "shares", "unit.share"}:

            return 1.0

    return STOCK_SHARES_PER_LOT





def build_code_multipliers(

    positions: list[dict[str, Any]],

    trades: list[dict[str, Any]],

    code_units: dict[str, float] | None = None,

) -> dict[str, float]:

    multipliers: dict[str, float] = {}

    contract_units = code_units or {}



    for position in positions:

        code = str(position.get("code") or "")

        if not code:

            continue

        mult = resolve_share_multiplier(position)

        # Trade replay uses lot size; Share rows must not overwrite Common.

        if mult == STOCK_SHARES_PER_LOT or code not in multipliers:

            multipliers[code] = mult



    for trade in trades:

        code = str(trade.get("code") or "")

        if not code or code in multipliers:

            continue

        multipliers[code] = contract_units.get(code, STOCK_SHARES_PER_LOT)



    return multipliers





def quantity_to_shares(

    record: dict[str, Any],

    multipliers: dict[str, float],

) -> float:

    code = str(record.get("code") or "")

    quantity = float(record.get("quantity") or 0)

    if record.get("unit") is not None:

        multiplier = resolve_share_multiplier(record)

    else:

        multiplier = multipliers.get(code, STOCK_SHARES_PER_LOT)

    if quantity > 0:

        return quantity * multiplier

    return 0.0





def position_market_value(

    position: dict[str, Any],

    multipliers: dict[str, float],

) -> tuple[float, str | None]:

    """Market value for one position row; returns (value, optional_warning)."""

    shares = quantity_to_shares(position, multipliers)

    if shares <= 0:

        return 0.0, None



    pnl = float(position.get("pnl") or 0)

    price = float(position.get("price") or 0)

    last_price = float(position.get("last_price") or 0)

    code = str(position.get("code") or "")



    if price > 0:

        return price * shares + pnl, None

    if last_price > 0:

        return last_price * shares, None

    if pnl != 0:

        return pnl, f"持倉 {code} 缺少 price/last_price，僅以 pnl 估算市值"



    return 0.0, f"持倉 {code} 無法估算市值（shares={shares:g}）"


def _is_share_unit(record: dict[str, Any]) -> bool:
    unit = str(record.get("unit") or "").lower()
    return unit in {"share", "shares", "unit.share"}


def combine_unit_shares(common_shares: float, share_shares: float) -> float:
    """Combine Common-lot and Share-unit rows without double counting.

    When both rows exist and share quantity >= common shares, the Share API row
    reports total shares (see broker inventory export), not an extra odd-lot slice.
    """
    if common_shares <= 0:
        return share_shares
    if share_shares <= 0:
        return common_shares
    if share_shares >= common_shares:
        return share_shares
    return common_shares + share_shares


def _position_group_key(position: dict[str, Any]) -> tuple[str, str]:
    code = str(position.get("code") or "")
    cond = str(position.get("cond") or "")
    return code, cond


def merge_position_rows(
    positions: list[dict[str, Any]],
    multipliers: dict[str, float],
) -> list[dict[str, Any]]:
    """Merge Common + Share rows by (code, cond); API duplicates pnl across unit rows."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for position in positions:
        code, cond = _position_group_key(position)
        if not code:
            continue
        groups[(code, cond)].append(position)

    merged: list[dict[str, Any]] = []
    for (code, cond), rows in sorted(groups.items()):
        common_shares = 0.0
        share_shares = 0.0
        for row in rows:
            shares = position_to_shares(row, multipliers)
            if shares <= 0:
                continue
            if _is_share_unit(row):
                share_shares += shares
            else:
                common_shares += shares

        total_shares = combine_unit_shares(common_shares, share_shares)
        if total_shares <= 0:
            continue

        share_is_total = common_shares > 0 and share_shares >= common_shares
        cost_sum = 0.0
        cost_shares = 0.0
        pnl = 0.0
        last_price = 0.0
        template = rows[0]

        for row in rows:
            shares = position_to_shares(row, multipliers)
            if shares <= 0:
                continue
            price = float(row.get("price") or 0)
            if price > 0 and not share_is_total:
                cost_sum += price * shares
                cost_shares += shares
            elif price > 0 and share_is_total and _is_share_unit(row):
                cost_sum = price * total_shares
                cost_shares = total_shares
            row_pnl = float(row.get("pnl") or 0)
            if row_pnl != 0:
                pnl = row_pnl
            row_last = float(row.get("last_price") or 0)
            if row_last > 0:
                last_price = row_last
            if shares > 0:
                template = row

        if share_is_total and cost_shares <= 0:
            price = float(template.get("price") or 0)
            if price > 0:
                cost_sum = price * total_shares
                cost_shares = total_shares

        avg_price = cost_sum / cost_shares if cost_shares > 0 else float(template.get("price") or 0)

        merged.append(
            {
                "code": code,
                "cond": cond,
                "direction": template.get("direction"),
                "unit": "Merged",
                "shares": total_shares,
                "price": avg_price,
                "last_price": last_price,
                "pnl": pnl,
            }
        )

    return merged


def merged_position_market_value(position: dict[str, Any]) -> tuple[float, str | None]:
    """Market value for a merged position row (pnl counted once)."""
    shares = float(position.get("shares") or 0)
    if shares <= 0:
        return 0.0, None

    pnl = float(position.get("pnl") or 0)
    price = float(position.get("price") or 0)
    last_price = float(position.get("last_price") or 0)
    code = str(position.get("code") or "")

    if last_price > 0:
        return last_price * shares, None
    if price > 0:
        return price * shares + pnl, None
    if pnl != 0:
        return pnl, f"持倉 {code} 缺少 price/last_price，僅以 pnl 估算市值"

    return 0.0, f"持倉 {code} 無法估算市值（shares={shares:g}）"


def merged_position_pnl_percent(position: dict[str, Any]) -> float | None:
    """Unrealized P&L % for a merged row: pnl / cost_basis × 100."""
    shares = float(position.get("shares") or 0)
    if shares <= 0:
        return None

    price = float(position.get("price") or 0)
    pnl = float(position.get("pnl") or 0)
    cost_basis = price * shares
    if cost_basis > 0:
        return pnl / cost_basis * 100.0

    last_price = float(position.get("last_price") or 0)
    if last_price > 0 and price > 0:
        return (last_price - price) / price * 100.0

    return None


def format_pnl_percent(pnl_pct: float | None) -> str:
    if pnl_pct is None:
        return "—"
    return f"{pnl_pct:+.2f}%"


def format_shares_lots(shares: float) -> str:
    """Format share count as lots + odd shares (e.g. 3張330股)."""
    total = int(shares)
    lots = total // int(STOCK_SHARES_PER_LOT)
    remainder = total % int(STOCK_SHARES_PER_LOT)
    if lots > 0 and remainder > 0:
        return f"{lots}張{remainder}股"
    if lots > 0:
        return f"{lots}張"
    return f"{remainder}股"





def calc_positions_market_value(

    positions: list[dict[str, Any]],

    multipliers: dict[str, float] | None = None,

) -> tuple[float, list[str]]:

    if multipliers is None:

        multipliers = build_code_multipliers(positions, [])



    total = 0.0

    warnings: list[str] = []

    for position in positions:

        value, warning = position_market_value(position, multipliers)

        total += value

        if warning:

            warnings.append(warning)

    return total, warnings





def position_to_shares(
    position: dict[str, Any],
    multipliers: dict[str, float],
) -> float:
    return quantity_to_shares(position, multipliers)



"""Query account positions with stock names and portfolio summary."""

from __future__ import annotations

from typing import Any

from shioaji.constant import Unit

from sino_account.core import session
from sino_account.core.serialize import resolve_stock_account, serialize
from sino_account.functions.get_settlements import get_settlements
from sino_account.functions.get_trading_limits import get_trading_limits
from sino_account.performance.analytics.quantity_units import (
    build_code_multipliers,
    format_pnl_percent,
    format_shares_lots,
    merge_position_rows,
    merged_position_market_value,
    merged_position_pnl_percent,
)
from sino_account.performance.data.contracts import build_code_units, resolve_stock_contract
from sino_account.performance.data.throttle import throttle


def _contracts_ready(api: Any) -> bool:
    contracts = getattr(api, "Contracts", None)
    if contracts is None:
        return False
    try:
        contracts.Stocks["2330"]
        return True
    except Exception:
        return False


def _serialize_share_positions(positions: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in positions:
        payload = serialize(item)
        if isinstance(payload, dict):
            payload["unit"] = "Share"
            rows.append(payload)
    return rows


def _lookup_stock_name(api: Any, code: str, cache: dict[str, str]) -> str:
    if code in cache:
        return cache[code]
    name = ""
    if _contracts_ready(api):
        try:
            contract = resolve_stock_contract(api, code)
            name = str(getattr(contract, "name", "") or "")
        except Exception:
            pass
    cache[code] = name
    return name


def _normalize_cond(cond: Any) -> str:
    if cond is None:
        return ""
    text = str(cond)
    if "." in text:
        return text.rsplit(".", 1)[-1]
    return text


def _empty_cond_summary() -> dict[str, float | int]:
    return {"count": 0, "market_value": 0.0, "pnl": 0.0}


def _parse_settlement_amounts(settlements: list[Any]) -> dict[str, Any]:
    """Extract T+1 / T+2 settlement amounts from api.settlements()."""
    parsed: dict[str, Any] = {
        "t1_amount": 0.0,
        "t2_amount": 0.0,
        "t1_date": None,
        "t2_date": None,
    }
    for item in settlements:
        if not isinstance(item, dict):
            continue
        t_day = item.get("T")
        if t_day is None:
            continue
        try:
            t_value = int(t_day)
        except (TypeError, ValueError):
            continue
        amount = float(item.get("amount") or 0)
        date = item.get("date")
        if t_value == 1:
            parsed["t1_amount"] = amount
            parsed["t1_date"] = date
        elif t_value == 2:
            parsed["t2_amount"] = amount
            parsed["t2_date"] = date
    return parsed


def _compute_nav_breakdown(
    acc_balance: float,
    cash_stock_market_value: float,
    margin_pnl: float,
    short_pnl: float,
    settlement_t1: float,
    settlement_t2: float,
) -> dict[str, float]:
    total_nav = (
        acc_balance
        + cash_stock_market_value
        + margin_pnl
        + short_pnl
        + settlement_t1
        + settlement_t2
    )
    return {
        "acc_balance": acc_balance,
        "cash_stock_market_value": cash_stock_market_value,
        "margin_pnl": margin_pnl,
        "short_pnl": short_pnl,
        "settlement_t1": settlement_t1,
        "settlement_t2": settlement_t2,
        "total_nav": total_nav,
    }


def get_positions2(account: Any | None = None) -> dict[str, Any]:
    """Return positions enriched with names, market value, and portfolio summary."""
    api = session.get_api()
    target = resolve_stock_account(api, account)
    contracts_ready = _contracts_ready(api)

    balance = serialize(api.account_balance(account=target))
    throttle()
    share_positions = api.list_positions(account=target, unit=Unit.Share)
    throttle()
    trading_limits = get_trading_limits(target)
    throttle()
    settlements = get_settlements(target)
    settlement_amounts = _parse_settlement_amounts(settlements)
    raw_positions = _serialize_share_positions(share_positions)

    codes = sorted({str(p.get("code") or "") for p in raw_positions if p.get("code")})
    code_units = build_code_units(api, codes) if codes and contracts_ready else {}
    multipliers = build_code_multipliers(raw_positions, [], code_units=code_units)
    positions = merge_position_rows(raw_positions, multipliers)
    name_cache: dict[str, str] = {}

    enriched: list[dict[str, Any]] = []
    total_market_value = 0.0
    cash_stock_market_value = 0.0
    total_unrealized_pnl = 0.0
    total_cost_basis = 0.0
    margin_summary = _empty_cond_summary()
    margin_summary["margin_purchase_amount"] = 0
    short_summary = _empty_cond_summary()
    short_summary["short_sale_margin"] = 0

    for position in positions:
        code = str(position.get("code") or "")
        shares = float(position.get("shares") or 0)
        market_value, mv_warning = merged_position_market_value(position)
        pnl = float(position.get("pnl") or 0)
        price = float(position.get("price") or 0)
        cost_basis = price * shares if price > 0 and shares > 0 else market_value - pnl

        row = dict(position)
        row["name"] = _lookup_stock_name(api, code, name_cache) if code else ""
        row["shares_lots"] = format_shares_lots(shares)
        row["unit_label"] = "Share（股）"
        row["market_value"] = market_value
        row["pnl_pct"] = merged_position_pnl_percent(position)
        if mv_warning:
            row["warning"] = mv_warning
        enriched.append(row)

        total_market_value += market_value
        total_unrealized_pnl += pnl
        if cost_basis > 0:
            total_cost_basis += cost_basis

        cond = _normalize_cond(position.get("cond"))
        if cond == "MarginTrading":
            margin_summary["count"] = int(margin_summary["count"]) + 1
            margin_summary["market_value"] = float(margin_summary["market_value"]) + market_value
            margin_summary["pnl"] = float(margin_summary["pnl"]) + pnl
            margin_summary["margin_purchase_amount"] = int(
                margin_summary.get("margin_purchase_amount") or 0
            ) + int(position.get("margin_purchase_amount") or 0)
        elif cond == "ShortSelling":
            short_summary["count"] = int(short_summary["count"]) + 1
            short_summary["market_value"] = float(short_summary["market_value"]) + market_value
            short_summary["pnl"] = float(short_summary["pnl"]) + pnl
            short_summary["short_sale_margin"] = int(
                short_summary.get("short_sale_margin") or 0
            ) + int(position.get("short_sale_margin") or 0)
        else:
            cash_stock_market_value += market_value

    acc_balance = float((balance or {}).get("acc_balance") or 0)
    margin_pnl = float(margin_summary.get("pnl") or 0)
    short_pnl = float(short_summary.get("pnl") or 0)
    settlement_t1 = float(settlement_amounts.get("t1_amount") or 0)
    settlement_t2 = float(settlement_amounts.get("t2_amount") or 0)
    nav_breakdown = _compute_nav_breakdown(
        acc_balance=acc_balance,
        cash_stock_market_value=cash_stock_market_value,
        margin_pnl=margin_pnl,
        short_pnl=short_pnl,
        settlement_t1=settlement_t1,
        settlement_t2=settlement_t2,
    )
    nav_breakdown["settlement_t1_date"] = settlement_amounts.get("t1_date")
    nav_breakdown["settlement_t2_date"] = settlement_amounts.get("t2_date")
    total_nav = float(nav_breakdown["total_nav"])
    total_pnl_pct = (
        total_unrealized_pnl / total_cost_basis * 100.0 if total_cost_basis > 0 else None
    )

    return {
        "balance": balance,
        "positions": enriched,
        "trading_limits": trading_limits,
        "settlements": settlements,
        "summary": {
            "acc_balance": acc_balance,
            "cash_stock_market_value": cash_stock_market_value,
            "total_market_value": total_market_value,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_pnl_pct": total_pnl_pct,
            "total_nav": total_nav,
            "nav_breakdown": nav_breakdown,
            "raw_count_share": len(share_positions),
            "raw_count_common": 0,
            "position_count_total": len(enriched),
            "contracts_ready": contracts_ready,
            "margin_trading": margin_summary,
            "short_selling": short_summary,
        },
    }


def _format_nav_component(label: str, value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"  {label:<34} {sign}{value:>14,.2f}"


def _format_settlement_label(base: str, settle_date: Any) -> str:
    date_text = str(settle_date or "").strip()
    if date_text:
        return f"{base} ({date_text})"
    return base


def format_positions2_report(data: dict[str, Any]) -> str:
    """Format positions report as readable text for GUI display."""
    summary = data.get("summary") or {}
    positions = data.get("positions") or []
    lines: list[str] = []

    lines.append("=== 持倉明細（list_positions Share 單位，股數） ===")
    header = (
        f"{'代號':<8} {'名稱':<10} {'張/股':>10} {'股數':>10} "
        f"{'成本價':>10} {'現價':>10} {'損益':>12} {'損益%':>8} {'市值':>14}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    for row in positions:
        code = str(row.get("code") or "")
        name = str(row.get("name") or "") or "(未知)"
        if len(name) > 10:
            name = name[:9] + "…"
        lines.append(
            f"{code:<8} {name:<10} {row.get('shares_lots', ''):>10} "
            f"{float(row.get('shares') or 0):>10.0f} "
            f"{float(row.get('price') or 0):>10.2f} "
            f"{float(row.get('last_price') or 0):>10.2f} "
            f"{float(row.get('pnl') or 0):>12.2f} "
            f"{format_pnl_percent(row.get('pnl_pct')):>8} "
            f"{float(row.get('market_value') or 0):>14.2f}"
        )
        cond = _normalize_cond(row.get("cond"))
        if cond == "MarginTrading":
            lines.append(
                f"  cond: {cond}  "
                f"總金額(市值): {float(row.get('market_value') or 0):>14,.2f}  "
                f"融資金額: {int(row.get('margin_purchase_amount') or 0):>12,}  "
                f"盈虧: {float(row.get('pnl') or 0):>12,.2f}"
            )
        elif cond == "ShortSelling":
            lines.append(
                f"  cond: {cond}  "
                f"總金額(市值): {float(row.get('market_value') or 0):>14,.2f}  "
                f"保證金: {int(row.get('short_sale_margin') or 0):>12,}  "
                f"盈虧: {float(row.get('pnl') or 0):>12,.2f}"
            )
        elif cond:
            lines.append(f"  cond: {cond}")
        warning = row.get("warning")
        if warning:
            lines.append(f"  ! {warning}")

    lines.append("")
    lines.append("=== 合計 ===")
    lines.append(f"現金餘額:       {float(summary.get('acc_balance') or 0):>14,.2f}")
    lines.append(f"現股市值:       {float(summary.get('cash_stock_market_value') or 0):>14,.2f}")
    lines.append(f"持倉市值:       {float(summary.get('total_market_value') or 0):>14,.2f}")
    lines.append(f"未實現損益:     {float(summary.get('total_unrealized_pnl') or 0):>14,.2f}")
    lines.append(f"未實現損益%:   {format_pnl_percent(summary.get('total_pnl_pct')):>14}")
    lines.append(
        f"持倉筆數: {int(summary.get('position_count_total') or 0)} "
        f"（API 原始列: Share {int(summary.get('raw_count_share') or 0)}）"
    )

    margin_summary = summary.get("margin_trading") or {}
    short_summary = summary.get("short_selling") or {}
    margin_count = int(margin_summary.get("count") or 0)
    short_count = int(short_summary.get("count") or 0)
    if margin_count or short_count:
        lines.append("")
        lines.append("=== 融資 / 融券持倉合計 ===")
        if margin_count:
            lines.append(
                f"融資 (MarginTrading): {margin_count:>3} 筆  "
                f"總金額(市值): {float(margin_summary.get('market_value') or 0):>14,.2f}  "
                f"融資金額: {int(margin_summary.get('margin_purchase_amount') or 0):>12,}  "
                f"盈虧: {float(margin_summary.get('pnl') or 0):>12,.2f}"
            )
        if short_count:
            lines.append(
                f"融券 (ShortSelling):  {short_count:>3} 筆  "
                f"總金額(市值): {float(short_summary.get('market_value') or 0):>14,.2f}  "
                f"保證金: {int(short_summary.get('short_sale_margin') or 0):>12,}  "
                f"盈虧: {float(short_summary.get('pnl') or 0):>12,.2f}"
            )

    limits = data.get("trading_limits") or {}
    lines.append("")
    lines.append("=== 融資 / 融券額度 ===")
    lines.append(
        f"融資:  上限 {int(limits.get('margin_limit') or 0):>12,}  "
        f"已用 {int(limits.get('margin_used') or 0):>12,}  "
        f"可用 {int(limits.get('margin_available') or 0):>12,}"
    )
    lines.append(
        f"融券:  上限 {int(limits.get('short_limit') or 0):>12,}  "
        f"已用 {int(limits.get('short_used') or 0):>12,}  "
        f"可用 {int(limits.get('short_available') or 0):>12,}"
    )
    limit_warning = str(limits.get("warning") or "").strip()
    if limit_warning:
        lines.append(f"  ! {limit_warning}")

    nav = summary.get("nav_breakdown") or {}
    lines.append("")
    lines.append("=== 總資產 (NAV) 計算 ===")
    lines.append(
        "公式: 現金 + 股價值 + 融資盈虧 + 融券盈虧 + T+1 交割款 + T+2 交割款"
    )
    lines.append(_format_nav_component("現金 (acc_balance)", float(nav.get("acc_balance") or 0)))
    lines.append(
        _format_nav_component("股價值（現股等）", float(nav.get("cash_stock_market_value") or 0))
    )
    lines.append(
        _format_nav_component(
            "融資 (MarginTrading) 盈虧",
            float(nav.get("margin_pnl") or 0),
        )
    )
    lines.append(
        _format_nav_component(
            "融券 (ShortSelling) 盈虧",
            float(nav.get("short_pnl") or 0),
        )
    )
    lines.append(
        _format_nav_component(
            _format_settlement_label("T+1 交割款", nav.get("settlement_t1_date")),
            float(nav.get("settlement_t1") or 0),
        )
    )
    lines.append(
        _format_nav_component(
            _format_settlement_label("T+2 交割款", nav.get("settlement_t2_date")),
            float(nav.get("settlement_t2") or 0),
        )
    )
    lines.append("  " + "-" * 52)
    lines.append(f"  {'總資產 (NAV)':<34} {float(summary.get('total_nav') or 0):>14,.2f}")

    if not summary.get("contracts_ready"):
        lines.append("")
        lines.append("提示: 商品檔未載入，股票名稱顯示為 (未知)。請 Logout 後重新 Login（會自動下載商品檔）。")
    elif not any(str(row.get("name") or "") for row in positions):
        lines.append("")
        lines.append("提示: 無法解析股票名稱，請確認商品檔是否完整。")

    return "\n".join(lines)

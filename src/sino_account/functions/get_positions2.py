"""Query account positions with stock names and portfolio summary."""

from __future__ import annotations

from typing import Any

from shioaji.constant import Unit

from sino_account.core import session
from sino_account.core.serialize import resolve_account, serialize
from sino_account.performance.analytics.quantity_units import (
    build_code_multipliers,
    format_shares_lots,
    merge_position_rows,
    merged_position_market_value,
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


def _merge_raw_positions(
    common_positions: list[Any],
    share_positions: list[Any],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for item in common_positions:
        payload = serialize(item)
        if isinstance(payload, dict):
            payload.setdefault("unit", "Common")
            merged.append(payload)
    for item in share_positions:
        payload = serialize(item)
        if isinstance(payload, dict):
            payload["unit"] = "Share"
            merged.append(payload)
    return merged


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


def get_positions2(account: Any | None = None) -> dict[str, Any]:
    """Return positions enriched with names, market value, and portfolio summary."""
    api = session.get_api()
    target = resolve_account(api, account)
    contracts_ready = _contracts_ready(api)

    balance = serialize(api.account_balance(account=target))
    throttle()
    common_positions = api.list_positions(account=target)
    throttle()
    share_positions = api.list_positions(account=target, unit=Unit.Share)
    raw_positions = _merge_raw_positions(common_positions, share_positions)

    codes = sorted({str(p.get("code") or "") for p in raw_positions if p.get("code")})
    code_units = build_code_units(api, codes) if codes and contracts_ready else {}
    multipliers = build_code_multipliers(raw_positions, [], code_units=code_units)
    positions = merge_position_rows(raw_positions, multipliers)
    name_cache: dict[str, str] = {}

    enriched: list[dict[str, Any]] = []
    total_market_value = 0.0
    total_unrealized_pnl = 0.0

    for position in positions:
        code = str(position.get("code") or "")
        shares = float(position.get("shares") or 0)
        market_value, mv_warning = merged_position_market_value(position)
        pnl = float(position.get("pnl") or 0)

        row = dict(position)
        row["name"] = _lookup_stock_name(api, code, name_cache) if code else ""
        row["shares_lots"] = format_shares_lots(shares)
        row["unit_label"] = "整股+零股"
        row["market_value"] = market_value
        if mv_warning:
            row["warning"] = mv_warning
        enriched.append(row)

        total_market_value += market_value
        total_unrealized_pnl += pnl

    acc_balance = float((balance or {}).get("acc_balance") or 0)
    total_nav = acc_balance + total_market_value

    return {
        "balance": balance,
        "positions": enriched,
        "summary": {
            "acc_balance": acc_balance,
            "total_market_value": total_market_value,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_nav": total_nav,
            "raw_count_common": len(common_positions),
            "raw_count_share": len(share_positions),
            "position_count_total": len(enriched),
            "contracts_ready": contracts_ready,
        },
    }


def format_positions2_report(data: dict[str, Any]) -> str:
    """Format positions report as readable text for GUI display."""
    summary = data.get("summary") or {}
    positions = data.get("positions") or []
    lines: list[str] = []

    lines.append("=== 持倉明細（整股+零股已合併） ===")
    header = (
        f"{'代號':<8} {'名稱':<10} {'張/股':>10} {'股數':>10} "
        f"{'成本價':>10} {'現價':>10} {'損益':>12} {'市值':>14}"
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
            f"{float(row.get('market_value') or 0):>14.2f}"
        )
        cond = row.get("cond")
        if cond:
            lines.append(f"  cond: {cond}")
        warning = row.get("warning")
        if warning:
            lines.append(f"  ! {warning}")

    lines.append("")
    lines.append("=== 合計 ===")
    lines.append(f"現金餘額:       {float(summary.get('acc_balance') or 0):>14,.2f}")
    lines.append(f"持倉市值:       {float(summary.get('total_market_value') or 0):>14,.2f}")
    lines.append(f"未實現損益:     {float(summary.get('total_unrealized_pnl') or 0):>14,.2f}")
    lines.append(f"總資產 (NAV):   {float(summary.get('total_nav') or 0):>14,.2f}")
    lines.append(
        f"持倉筆數: {int(summary.get('position_count_total') or 0)} "
        f"（API 原始列: 整股 {int(summary.get('raw_count_common') or 0)} "
        f"+ 零股 {int(summary.get('raw_count_share') or 0)}）"
    )

    if not summary.get("contracts_ready"):
        lines.append("")
        lines.append("提示: 商品檔未載入，股票名稱顯示為 (未知)。請 Logout 後重新 Login（會自動下載商品檔）。")
    elif not any(str(row.get("name") or "") for row in positions):
        lines.append("")
        lines.append("提示: 無法解析股票名稱，請確認商品檔是否完整。")

    return "\n".join(lines)

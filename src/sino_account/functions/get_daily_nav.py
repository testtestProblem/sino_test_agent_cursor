"""Historical daily total assets (NAV) using closing prices.

Holdings are reconstructed exactly from the broker exports:
- 庫存.xlsx   provides current holdings (今日餘額, shares).
- 對帳單.xlsx provides every buy/sell, so daily holdings = current inventory
  walked backward through trades.

Each held stock is valued at its daily closing price (last minute-bar Close).
Non-trading days (no kbar for the calendar code 2330) are skipped.
"""

from __future__ import annotations

from typing import Any

from sino_account.core import session
from sino_account.core.serialize import extract_acc_balance, resolve_stock_account, serialize
from sino_account.functions.get_profit_loss import default_date_range
from sino_account.functions.get_stock_kbars import aggregate_daily_open_close, get_stock_kbars
from sino_account.performance.data.statements import (
    load_inventory,
    load_statement,
    reconstruct_cash_on,
    reconstruct_holdings_on,
)
from sino_account.performance.data.throttle import throttle

CALENDAR_CODE = "2330"


def _daily_close_map_from_kbars(code: str, start: str, end: str) -> dict[str, float]:
    data = get_stock_kbars(code, start, end)
    daily_bars = aggregate_daily_open_close(list(data.get("bars") or []))
    return {str(row.get("date") or ""): float(row.get("close") or 0) for row in daily_bars}


def _fetch_ending_cash(api: Any, target: Any) -> tuple[float, dict[str, Any]]:
    throttle()
    raw = api.account_balance(account=target)
    balance = serialize(raw)
    ending_cash = extract_acc_balance(raw)
    if ending_cash == 0.0:
        ending_cash = extract_acc_balance(balance if isinstance(balance, dict) else {})
    return ending_cash, balance if isinstance(balance, dict) else {}


def get_daily_nav_history(
    account: Any | None = None,
    start: str | None = None,
    end: str | None = None,
    *,
    statement_path: str | None = None,
    inventory_path: str | None = None,
) -> dict[str, Any]:
    """Estimate daily NAV = cash + holdings valued at daily close (trading days only).

    Holdings come from 庫存.xlsx + 對帳單.xlsx; prices come from kbars.
    """
    api = session.get_api()
    target = resolve_stock_account(api, account)

    if start is None or end is None:
        default_begin, default_end = default_date_range()
        start = start or default_begin
        end = end or default_end

    warnings: list[str] = []

    inventory = load_inventory(inventory_path)
    trades = load_statement(statement_path)
    inv_now: dict[str, float] = inventory.get("holdings", {})
    names: dict[str, str] = inventory.get("names", {})
    snapshot_market_value = float(inventory.get("total_market_value") or 0.0)

    statement_dates = [t["date"] for t in trades if t.get("date")]
    statement_min = min(statement_dates) if statement_dates else None
    if statement_min and start < statement_min:
        warnings.append(
            f"查詢起始日 {start} 早於對帳單最早交易日 {statement_min}，"
            f"{statement_min} 之前的持倉以該日往前的庫存推估（視為區間外不變）。"
        )

    ending_cash, balance = _fetch_ending_cash(api, target)

    throttle()
    calendar_closes = _daily_close_map_from_kbars(CALENDAR_CODE, start, end)
    trading_days = sorted(day for day in calendar_closes if start <= day <= end)

    if not trading_days:
        warnings.append(f"找不到交易日曆 {CALENDAR_CODE} 的 kbars（請確認 Login fetch_contract=True 與日期）。")

    daily_holdings: dict[str, dict[str, float]] = {}
    needed_codes: set[str] = set()
    for day in trading_days:
        holdings = reconstruct_holdings_on(inv_now, trades, day)
        daily_holdings[day] = holdings
        needed_codes.update(holdings.keys())

    close_map: dict[str, dict[str, float]] = {CALENDAR_CODE: calendar_closes}
    for code in sorted(needed_codes):
        if code == CALENDAR_CODE:
            continue
        try:
            throttle()
            closes = _daily_close_map_from_kbars(code, start, end)
            if closes:
                close_map[code] = closes
            else:
                close_map[code] = {}
                warnings.append(f"無收盤價資料: {code}")
        except Exception as exc:
            close_map[code] = {}
            warnings.append(f"無法取得 {code} kbars: {exc}")

    points: list[dict[str, Any]] = []
    skipped_missing_close: list[str] = []

    for day in trading_days:
        holdings = daily_holdings.get(day, {})
        active = {code: shares for code, shares in holdings.items() if abs(shares) > 1e-9}

        market_value = 0.0
        missing: list[str] = []
        for code, shares in active.items():
            close = close_map.get(code, {}).get(day)
            if close is None:
                missing.append(code)
                continue
            market_value += shares * close

        if missing:
            skipped_missing_close.append(day)
            continue

        cash = reconstruct_cash_on(ending_cash, trades, day)
        points.append(
            {
                "date": day,
                "cash": cash,
                "market_value": market_value,
                "nav": cash + market_value,
                "position_count": len(active),
            }
        )

    if skipped_missing_close:
        sample = ", ".join(skipped_missing_close[:6])
        suffix = "..." if len(skipped_missing_close) > 6 else ""
        warnings.append(
            f"{len(skipped_missing_close)} 個交易日因部分持股缺收盤價而略過: {sample}{suffix}"
        )

    snapshot_nav = ending_cash + snapshot_market_value
    if points and snapshot_market_value > 0:
        last = points[-1]
        kbars_mv = float(last.get("market_value") or 0)
        if snapshot_nav > 0:
            deviation = abs(kbars_mv - snapshot_market_value) / snapshot_nav
            if deviation > 0.05:
                warnings.append(
                    f"最後一日重建持倉市值 {kbars_mv:,.0f} 與庫存現值 {snapshot_market_value:,.0f} "
                    f"偏差 {deviation * 100:.1f}%（可能因收盤價來源或除權息差異）。"
                )

    status = str((balance or {}).get("status") or "")
    errmsg = str((balance or {}).get("errmsg") or "").strip()
    if errmsg:
        warnings.append(errmsg)
    elif ending_cash == 0.0 and status and status != "Fetched":
        warnings.append(f"account_balance 狀態: {status}")
    warnings.append(
        "現金以目前 account_balance 往回扣對帳單買賣推估（未含股息、入金、出金）。"
    )

    return {
        "start": start,
        "end": end,
        "ending_cash": ending_cash,
        "snapshot_market_value": snapshot_market_value,
        "snapshot_nav": snapshot_nav,
        "trading_day_count": len(points),
        "skipped_non_trading_days": True,
        "calendar_code": CALENDAR_CODE,
        "inventory_codes": len(inv_now),
        "trade_count": len(trades),
        "names": names,
        "points": points,
        "warnings": warnings,
    }


def format_daily_nav_report(data: dict[str, Any]) -> str:
    """Format daily NAV history as a readable table."""
    points: list[dict[str, Any]] = list(data.get("points") or [])
    warnings: list[str] = list(data.get("warnings") or [])
    lines: list[str] = []

    ending_cash = float(data.get("ending_cash") or 0)

    lines.append("=== 歷史每日總資產（收盤價結算） ===")
    lines.append(f"區間: {data.get('start')} ~ {data.get('end')}")
    lines.append(f"交易日數: {data.get('trading_day_count', len(points))}")
    lines.append(
        f"資料來源: 庫存.xlsx（{data.get('inventory_codes', 0)} 檔） + "
        f"對帳單.xlsx（{data.get('trade_count', 0)} 筆交易）"
    )
    lines.append(f"期末現金: {ending_cash:,.2f}（account_balance）")
    snapshot_nav = float(data.get("snapshot_nav") or 0)
    snapshot_mv = float(data.get("snapshot_market_value") or 0)
    if snapshot_mv > 0:
        lines.append(
            f"庫存現值快照: {snapshot_mv:,.2f}；快照 NAV: {snapshot_nav:,.2f}"
            f"（現金 {ending_cash:,.2f} + 持倉 {snapshot_mv:,.2f}）"
        )
    lines.append(f"交易日曆: {data.get('calendar_code')} 有 kbars 之日期（休市日不列入）")

    if not points:
        lines.append("")
        lines.append("（無資料，請確認 Login、日期區間、Excel 檔案與 kbars 是否可用）")
    else:
        header = f"{'日期':<12} {'現金':>14} {'持倉市值':>14} {'總資產':>14} {'持倉檔數':>8}"
        lines.append("")
        lines.append(header)
        lines.append("-" * len(header))
        for row in points:
            lines.append(
                f"{str(row.get('date') or ''):<12} "
                f"{float(row.get('cash') or 0):>14,.2f} "
                f"{float(row.get('market_value') or 0):>14,.2f} "
                f"{float(row.get('nav') or 0):>14,.2f} "
                f"{int(row.get('position_count') or 0):>8}"
            )

    if warnings:
        lines.append("")
        lines.append("=== 提示 ===")
        for warning in warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines)

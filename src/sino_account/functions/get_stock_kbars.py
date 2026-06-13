"""Query stock historical K-bar (OHLCV) data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sino_account.core import session
from sino_account.core.serialize import serialize
from sino_account.functions.get_profit_loss import default_date_range
from sino_account.performance.data.contracts import resolve_stock_contract


def _format_bar_time(ts: Any) -> str:
    if ts is None:
        return ""
    try:
        value = int(ts)
        if value > 10**18:
            seconds = value / 1_000_000_000
        elif value > 10**15:
            seconds = value / 1_000_000
        else:
            seconds = float(value)
        return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError, OverflowError):
        return str(ts)


def _parse_kbars_rows(kbars: Any) -> list[dict[str, Any]]:
    data = serialize(kbars)
    if not isinstance(data, dict):
        return []

    ts_list = data.get("ts") or data.get("datetime") or []
    field_names = ("Open", "High", "Low", "Close", "Volume", "Amount")
    arrays = {name: data.get(name) or [] for name in field_names}

    rows: list[dict[str, Any]] = []
    for index, ts in enumerate(ts_list):
        row: dict[str, Any] = {
            "datetime": _format_bar_time(ts),
            "ts": ts,
        }
        for name, values in arrays.items():
            if index < len(values):
                row[name] = values[index]
        rows.append(row)
    return rows


def _bar_trading_date(bar: dict[str, Any]) -> str:
    dt = str(bar.get("datetime") or "")
    if len(dt) >= 10:
        return dt[:10]
    return dt


def aggregate_daily_open_close(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse minute bars into one row per day: first Open, last Close."""
    daily: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for bar in bars:
        date_key = _bar_trading_date(bar)
        if not date_key:
            continue

        open_price = float(bar.get("Open") or 0)
        close_price = float(bar.get("Close") or 0)
        if date_key not in daily:
            daily[date_key] = {
                "date": date_key,
                "open": open_price,
                "close": close_price,
            }
            order.append(date_key)
        else:
            daily[date_key]["close"] = close_price

    return [daily[date_key] for date_key in order]


def get_stock_kbars(
    code: str,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Fetch minute K-bars for a stock code between start and end (YYYY-MM-DD)."""
    api = session.get_api()
    stock_code = str(code or "").strip()
    if not stock_code:
        raise ValueError("請輸入股票代號")

    if start is None or end is None:
        default_begin, default_end = default_date_range()
        start = start or default_begin
        end = end or default_end

    contract = resolve_stock_contract(api, stock_code)
    kbars = api.kbars(contract=contract, start=start, end=end)
    rows = _parse_kbars_rows(kbars)

    return {
        "code": stock_code,
        "name": str(getattr(contract, "name", "") or ""),
        "start": start,
        "end": end,
        "bar_count": len(rows),
        "bars": rows,
    }


def get_stock_kbars2(
    code: str,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Fetch kbars and return daily open/close only."""
    data = get_stock_kbars(code, start, end)
    daily_bars = aggregate_daily_open_close(list(data.get("bars") or []))
    return {
        "code": data.get("code"),
        "name": data.get("name"),
        "start": data.get("start"),
        "end": data.get("end"),
        "day_count": len(daily_bars),
        "daily_bars": daily_bars,
    }


def format_kbars_report(data: dict[str, Any], max_rows: int = 80) -> str:
    """Format kbars as a readable table for GUI display."""
    code = str(data.get("code") or "")
    name = str(data.get("name") or "") or "(未知)"
    bars: list[dict[str, Any]] = list(data.get("bars") or [])
    lines: list[str] = []

    lines.append(f"=== 股票歷史行情 K 線 ({code} {name}) ===")
    lines.append(f"區間: {data.get('start')} ~ {data.get('end')}")
    lines.append(f"筆數: {data.get('bar_count', len(bars))}")

    if not bars:
        lines.append("")
        lines.append("（無資料，請確認已 Login 且 fetch_contract=True，或調整日期區間）")
        return "\n".join(lines)

    header = (
        f"{'時間':<20} {'開':>10} {'高':>10} {'低':>10} "
        f"{'收':>10} {'量':>10} {'額':>14}"
    )
    lines.append("")
    lines.append(header)
    lines.append("-" * len(header))

    display_head = bars
    display_tail: list[dict[str, Any]] = []
    if len(bars) > max_rows:
        head_count = max_rows // 2
        tail_count = max_rows - head_count
        display_head = bars[:head_count]
        display_tail = bars[-tail_count:] if tail_count > 0 else []

    def append_row(row: dict[str, Any]) -> None:
        lines.append(
            f"{str(row.get('datetime') or ''):<20} "
            f"{float(row.get('Open') or 0):>10.2f} "
            f"{float(row.get('High') or 0):>10.2f} "
            f"{float(row.get('Low') or 0):>10.2f} "
            f"{float(row.get('Close') or 0):>10.2f} "
            f"{int(float(row.get('Volume') or 0)):>10} "
            f"{float(row.get('Amount') or 0):>14.0f}"
        )

    for row in display_head:
        append_row(row)

    omitted = len(bars) - len(display_head) - len(display_tail)
    if omitted > 0:
        lines.append(f"... 省略中間 {omitted} 筆 ...")

    for row in display_tail:
        append_row(row)

    return "\n".join(lines)


def format_kbars2_report(data: dict[str, Any]) -> str:
    """Format daily open/close table for GUI display."""
    code = str(data.get("code") or "")
    name = str(data.get("name") or "") or "(未知)"
    daily_bars: list[dict[str, Any]] = list(data.get("daily_bars") or [])
    lines: list[str] = []

    lines.append(f"=== 股票日 K 開收盤 ({code} {name}) ===")
    lines.append(f"區間: {data.get('start')} ~ {data.get('end')}")
    lines.append(f"交易日數: {data.get('day_count', len(daily_bars))}")

    if not daily_bars:
        lines.append("")
        lines.append("（無資料，請確認已 Login 且 fetch_contract=True，或調整日期區間）")
        return "\n".join(lines)

    header = f"{'日期':<12} {'開盤':>12} {'收盤':>12}"
    lines.append("")
    lines.append(header)
    lines.append("-" * len(header))

    for row in daily_bars:
        open_price = float(row.get("open") or 0)
        close_price = float(row.get("close") or 0)
        lines.append(
            f"{str(row.get('date') or ''):<12} "
            f"{open_price:>12.2f} "
            f"{close_price:>12.2f}"
        )

    return "\n".join(lines)

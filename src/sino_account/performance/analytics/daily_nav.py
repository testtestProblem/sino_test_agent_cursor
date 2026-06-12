"""Build daily NAV time series for capital level chart."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from sino_account.functions.get_settlements import get_settlements
from sino_account.performance.analytics.daily_closes import (
    build_daily_close_map,
    get_close_on_day,
)
from sino_account.performance.analytics.holdings_timeline import build_holdings_timeline
from sino_account.performance.analytics.unrealized import (
    calc_cash_balance,
    calc_ending_nav,
    calc_position_market_value_with_warnings,
)
from sino_account.performance.data.collect_snapshot import collect_snapshot
from sino_account.performance.data.contracts import build_code_units
from sino_account.performance.data.get_profit_loss_range import get_profit_loss_range
from sino_account.performance.data.get_stock_kbars import get_stock_kbars_batch
from sino_account.performance.date_range import iter_dates, three_month_range
from sino_account.performance.models import DailyNavPoint, DailyNavSeries
from sino_account.performance.session import ensure_performance_session


def _normalize_settlement_date(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else text


def _extract_codes(trades: list[dict[str, Any]], positions: list[dict[str, Any]]) -> list[str]:
    codes: set[str] = set()
    for trade in trades:
        code = str(trade.get("code") or "")
        if code:
            codes.add(code)
    for position in positions:
        code = str(position.get("code") or "")
        if code:
            codes.add(code)
    return sorted(codes)


def calc_daily_cash(
    ending_cash: float,
    settlements: list[dict[str, Any]],
    day: str,
    *,
    end: str,
    use_settlement_adjustment: bool = False,
) -> float:
    """Estimate cash on a given day."""
    if not use_settlement_adjustment:
        return ending_cash

    future_amount = 0.0
    for item in settlements:
        settlement_date = _normalize_settlement_date(item.get("date"))
        if settlement_date and settlement_date > day:
            future_amount += float(item.get("amount") or 0)
    return ending_cash - future_amount


def calc_daily_market_value(
    holdings: dict[str, float],
    close_map: dict[str, dict[str, float]],
    day: str,
) -> float:
    """Sum market value; holdings values are share counts (supports odd lots)."""
    total = 0.0
    for code, shares in holdings.items():
        if shares <= 0:
            continue
        code_closes = close_map.get(code)
        if not code_closes:
            continue
        close = get_close_on_day(code_closes, day)
        if close is None:
            continue
        total += shares * close
    return total


def build_daily_nav_series_from_data(
    *,
    trades: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    balance: dict[str, Any],
    settlements: list[dict[str, Any]],
    kbars_by_code: dict[str, dict[str, Any]],
    start: str,
    end: str,
    code_units: dict[str, float] | None = None,
    snapshot_meta: dict[str, Any] | None = None,
) -> DailyNavSeries:
    warnings: list[str] = []
    ending_cash = calc_cash_balance(balance)
    position_mv, mv_warnings = calc_position_market_value_with_warnings(
        positions,
        code_units=code_units,
    )
    warnings.extend(mv_warnings)
    snapshot_nav = calc_ending_nav(ending_cash, position_mv)

    warnings.append("現金曲線以期末 acc_balance 近似整段區間（非歷史交割還原）。")

    if snapshot_meta:
        common_count = int(snapshot_meta.get("position_count_common") or 0)
        share_count = int(snapshot_meta.get("position_count_share") or 0)
        if share_count > 0:
            warnings.append(f"已合併零股持倉 {share_count} 筆（整股 {common_count} 筆）。")

    holdings_timeline, replay_warnings = build_holdings_timeline(
        trades,
        positions,
        start,
        end,
        code_units=code_units,
    )
    warnings.extend(replay_warnings)
    close_map, close_warnings = build_daily_close_map(kbars_by_code, start, end)
    warnings.extend(close_warnings)

    missing_codes = {
        code
        for day in iter_dates(start, end)
        for code, quantity in holdings_timeline[day].items()
        if quantity > 0 and code not in close_map
    }
    for code in sorted(missing_codes):
        warnings.append(f"持倉標的缺少收盤價，市值略過: {code}")

    points: list[DailyNavPoint] = []
    for day in iter_dates(start, end):
        holdings = holdings_timeline[day]
        cash = calc_daily_cash(ending_cash, settlements, day, end=end)
        market_value = calc_daily_market_value(holdings, close_map, day)
        nav = cash + market_value
        points.append(
            DailyNavPoint(
                date=day,
                nav=nav,
                cash=cash,
                market_value=market_value,
            )
        )

    if points:
        last_point = points[-1]
        chart_market_before = last_point.market_value
        points[-1] = DailyNavPoint(
            date=end,
            cash=ending_cash,
            market_value=position_mv,
            nav=snapshot_nav,
        )
        if snapshot_nav > 0:
            deviation = abs(chart_market_before - position_mv) / snapshot_nav
            if deviation > 0.05:
                warnings.append(
                    "kbars 估算期末持倉市值與快照偏差超過 5%，最後一日已錨定為快照值。"
                )
                if missing_codes:
                    warnings.append(
                        f"可能缺 kbars 的標的: {', '.join(sorted(missing_codes))}"
                    )

    return DailyNavSeries(
        start=start,
        end=end,
        points=points,
        warnings=warnings,
        snapshot_cash=ending_cash,
        snapshot_market_value=position_mv,
        snapshot_nav=snapshot_nav,
    )


def build_daily_nav_series(
    account: Any | None = None,
    start: str | None = None,
    end: str | None = None,
    *,
    fetch_kbars: bool = True,
) -> DailyNavSeries:
    ensure_performance_session()

    if start is None or end is None:
        start, end = three_month_range(end)

    trades = get_profit_loss_range(account, start, end)
    snapshot = collect_snapshot(account)
    settlements = get_settlements(account)

    positions = snapshot.get("positions") or []
    balance = snapshot.get("balance") or {}

    codes = _extract_codes(trades, positions)
    code_units: dict[str, float] = {}
    if codes:
        from sino_account.core import session

        code_units = build_code_units(session.get_api(), codes)

    kbars_by_code: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    if fetch_kbars:
        if codes:
            batch = get_stock_kbars_batch(codes, start, end)
            kbars_by_code = batch.get("kbars") or {}
            for code, error in (batch.get("errors") or {}).items():
                warnings.append(f"kbars 查詢失敗 {code}: {error}")
    else:
        warnings.append("已略過 kbars 查詢（fetch_kbars=False）。")

    series = build_daily_nav_series_from_data(
        trades=trades,
        positions=positions,
        balance=balance,
        settlements=settlements,
        kbars_by_code=kbars_by_code,
        start=start,
        end=end,
        code_units=code_units,
        snapshot_meta=snapshot,
    )
    series.warnings = warnings + series.warnings
    return series


def main() -> None:
    parser = argparse.ArgumentParser(description="Print daily NAV series for debugging.")
    parser.add_argument("--start", help="Period start date (YYYY-MM-DD).")
    parser.add_argument("--end", help="Period end date (YYYY-MM-DD).")
    parser.add_argument(
        "--no-kbars",
        action="store_true",
        help="Skip kbars queries (market value will be zero).",
    )
    args = parser.parse_args()

    try:
        series = build_daily_nav_series(
            start=args.start,
            end=args.end,
            fetch_kbars=not args.no_kbars,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Daily NAV series: {series.start} ~ {series.end}")
    print(series.method_note)
    if series.snapshot_nav is not None:
        print(
            f"Snapshot NAV: {series.snapshot_nav:,.2f} "
            f"(cash={series.snapshot_cash:,.2f}, market={series.snapshot_market_value:,.2f})"
        )
    for point in series.points:
        print(
            f"{point.date}  nav={point.nav:,.2f}  "
            f"cash={point.cash:,.2f}  market={point.market_value:,.2f}"
        )
    if series.warnings:
        print("\nWarnings:")
        for warning in series.warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()

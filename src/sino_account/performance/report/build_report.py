"""Build 3-month performance report."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Any

from sino_account.core import session
from sino_account.core.serialize import account_info
from sino_account.functions.get_settlements import get_settlements
from sino_account.performance.accounts import ensure_stock_account
from sino_account.performance.analytics.benchmark import calc_benchmark_return_pct
from sino_account.performance.analytics.by_stock import build_by_stock
from sino_account.performance.analytics.cashflow import calc_net_cash_flow
from sino_account.performance.analytics.portfolio_return import (
    calc_estimated_beginning_nav,
    calc_excess_return_pct,
    calc_portfolio_return_pct,
)
from sino_account.performance.analytics.realized import calc_realized_pnl_total
from sino_account.performance.analytics.unrealized import (
    calc_cash_balance,
    calc_ending_nav,
    calc_position_market_value,
    calc_unrealized_pnl_total,
)
from sino_account.performance.data.collect_snapshot import collect_snapshot
from sino_account.performance.data.get_benchmark_kbars import get_benchmark_kbars
from sino_account.performance.data.get_profit_loss_range import get_profit_loss_range
from sino_account.performance.data.get_profit_loss_summary import get_profit_loss_summary
from sino_account.performance.data.get_stock_kbars import get_stock_kbars_batch
from sino_account.performance.date_range import three_month_range
from sino_account.performance.models import (
    AccountRef,
    PerformanceMeta,
    PerformanceReport,
    PerformanceSummary,
    Period,
)
from sino_account.performance.paths import project_root
from sino_account.performance.report.export_json import export_json
from sino_account.performance.report.export_markdown import export_markdown
from sino_account.performance.session import ensure_performance_session, logout_performance


def _resolve_stock_account(account: Any | None) -> Any:
    api = session.get_api()
    if account is not None:
        ensure_stock_account(account)
        return account

    if api.stock_account is not None:
        ensure_stock_account(api.stock_account)
        return api.stock_account

    for item in api.list_accounts():
        try:
            ensure_stock_account(item)
            return item
        except ValueError:
            continue

    raise RuntimeError("找不到證券帳戶")


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


def run_report(
    account: Any | None = None,
    start: str | None = None,
    end: str | None = None,
    *,
    fetch_kbars: bool = True,
) -> PerformanceReport:
    ensure_performance_session()

    if start is None or end is None:
        start, end = three_month_range(end)

    target = _resolve_stock_account(account)
    warnings: list[str] = []

    trades = get_profit_loss_range(target, start, end)
    summary = get_profit_loss_summary(target, start, end)
    snapshot = collect_snapshot(target)
    settlements = get_settlements(target)

    positions = snapshot.get("positions") or []
    balance = snapshot.get("balance") or {}

    realized_pnl_total = calc_realized_pnl_total(trades)
    unrealized_pnl_total = calc_unrealized_pnl_total(positions)
    cash_balance = calc_cash_balance(balance)
    position_market_value = calc_position_market_value(positions)
    ending_nav = calc_ending_nav(cash_balance, position_market_value)
    net_cash_flow = calc_net_cash_flow(settlements, start, end)

    estimated_beginning_nav = calc_estimated_beginning_nav(
        ending_nav,
        realized_pnl_total,
        unrealized_pnl_total,
        net_cash_flow,
    )
    portfolio_return_pct = calc_portfolio_return_pct(
        ending_nav,
        estimated_beginning_nav,
        net_cash_flow,
    )
    if estimated_beginning_nav is None:
        warnings.append("期初淨資產估算 <= 0，組合報酬率無法計算。")

    benchmark_return_pct: float | None = None
    if fetch_kbars:
        try:
            benchmark_kbars = get_benchmark_kbars(start, end)
            benchmark_return_pct = calc_benchmark_return_pct(benchmark_kbars, start, end)
            if benchmark_return_pct is None:
                warnings.append("大盤 kbars 資料不足，無法計算 benchmark_return_pct。")
        except Exception as exc:
            warnings.append(f"大盤行情查詢失敗: {exc}")

        codes = _extract_codes(trades, positions)
        if codes:
            try:
                batch = get_stock_kbars_batch(codes, start, end)
                for code, error in (batch.get("errors") or {}).items():
                    warnings.append(f"個股 kbars 查詢失敗 {code}: {error}")
            except Exception as exc:
                warnings.append(f"個股行情查詢失敗: {exc}")
    else:
        warnings.append("已略過 kbars 查詢（fetch_kbars=False）。")

    excess_return_pct = calc_excess_return_pct(portfolio_return_pct, benchmark_return_pct)
    by_stock = build_by_stock(trades, positions, summary)

    info = account_info(target)
    return PerformanceReport(
        meta=PerformanceMeta(
            generated_at=datetime.now().isoformat(timespec="seconds"),
            account=AccountRef(
                broker_id=str(info.get("broker_id") or ""),
                account_id=str(info.get("account_id") or ""),
                account_type=str(info.get("account_type") or "S"),
            ),
        ),
        period=Period(start=start, end=end),
        summary=PerformanceSummary(
            realized_pnl_total=realized_pnl_total,
            unrealized_pnl_total=unrealized_pnl_total,
            cash_balance=cash_balance,
            position_market_value=position_market_value,
            ending_nav=ending_nav,
            net_cash_flow=net_cash_flow,
            estimated_beginning_nav=estimated_beginning_nav,
            portfolio_return_pct=portfolio_return_pct,
            benchmark_return_pct=benchmark_return_pct,
            excess_return_pct=excess_return_pct,
        ),
        by_stock=by_stock,
        trades=trades,
        warnings=warnings,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate 3-month stock performance report.")
    parser.add_argument("--start", help="Period start date (YYYY-MM-DD). Default: 3 months before today.")
    parser.add_argument("--end", help="Period end date (YYYY-MM-DD). Default: today.")
    parser.add_argument(
        "--output",
        default=str(project_root() / "reports"),
        help="Output directory for report_3m.json and report_3m.md",
    )
    parser.add_argument(
        "--keep-session",
        action="store_true",
        help="Do not logout after report generation.",
    )
    args = parser.parse_args()

    was_logged_in = session.is_logged_in()
    try:
        report = run_report(start=args.start, end=args.end)
        json_path = export_json(report, args.output)
        md_path = export_markdown(report, args.output)

        print(f"JSON: {json_path}")
        print(f"Markdown: {md_path}")
        if report.warnings:
            print("Warnings:", file=sys.stderr)
            for warning in report.warnings:
                print(f"  - {warning}", file=sys.stderr)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        if not was_logged_in and not args.keep_session:
            logout_performance()


if __name__ == "__main__":
    main()

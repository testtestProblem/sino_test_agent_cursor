"""Unit tests for performance analytics (no API required)."""

from sino_account.performance.analytics.benchmark import calc_benchmark_return_pct
from sino_account.performance.analytics.by_stock import build_by_stock
from sino_account.performance.analytics.portfolio_return import (
    calc_estimated_beginning_nav,
    calc_portfolio_return_pct,
)
from sino_account.performance.analytics.realized import calc_realized_pnl_total
from sino_account.performance.analytics.unrealized import calc_position_market_value


def test_realized_and_portfolio_return() -> None:
    trades = [{"code": "2330", "pnl": 1000}, {"code": "2890", "pnl": -200}]
    assert calc_realized_pnl_total(trades) == 800

    beginning = calc_estimated_beginning_nav(
        ending_nav=1_000_000,
        realized_pnl_total=800,
        unrealized_pnl_total=5000,
        net_cash_flow=10_000,
    )
    assert beginning == 1_004_200

    ret = calc_portfolio_return_pct(1_000_000, beginning, 10_000)
    assert ret is not None
    assert round(ret, 4) == round((1_000_000 - 1_004_200 - 10_000) / 1_004_200 * 100, 4)


def test_benchmark_return() -> None:
    kbars = {
        "datetime": ["2026-03-06", "2026-03-07", "2026-06-06"],
        "Close": [100.0, 101.0, 110.0],
    }
    result = calc_benchmark_return_pct(kbars, "2026-03-06", "2026-06-06")
    assert result == 10.0


def test_benchmark_return_with_nanosecond_ts() -> None:
    kbars = {
        "ts": [1772784000000000000, 1772870400000000000],
        "Close": [100.0, 110.0],
    }
    result = calc_benchmark_return_pct(kbars, "2026-03-06", "2026-03-07")
    assert result == 10.0


def test_position_market_value_uses_lot_size() -> None:
    positions = [
        {"code": "2890", "quantity": 1, "price": 30.0, "last_price": 31.0, "pnl": 1000},
        {"code": "2330", "quantity": 1, "price": 2000.0, "last_price": 1980.0, "pnl": -20000},
        {"code": "empty", "quantity": 0, "price": 100.0, "last_price": 110.0, "pnl": 0},
    ]
    # price * shares + pnl (not last_price * shares)
    assert calc_position_market_value(positions) == 31_000 + 1_980_000


def test_by_stock() -> None:
    trades = [{"code": "2330", "pnl": 100}, {"code": "2330", "pnl": 50}]
    positions = [{"code": "2330", "pnl": 20}]
    summary = {
        "profitloss_summary": [{"code": "2330", "pnl": 150, "pr_ratio": 0.05}],
    }
    rows = build_by_stock(trades, positions, summary)
    assert len(rows) == 1
    assert rows[0].code == "2330"
    assert rows[0].realized_pnl == 150
    assert rows[0].unrealized_pnl == 20
    assert rows[0].trade_count == 2


if __name__ == "__main__":
    test_realized_and_portfolio_return()
    test_benchmark_return()
    test_benchmark_return_with_nanosecond_ts()
    test_position_market_value_uses_lot_size()
    test_by_stock()
    print("analytics tests passed")

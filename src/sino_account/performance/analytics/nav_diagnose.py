"""Diagnostic breakdown for snapshot NAV vs chart estimates."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from sino_account.performance.analytics.quantity_units import (
    build_code_multipliers,
    position_market_value,
    position_to_shares,
)
from sino_account.performance.analytics.unrealized import (
    calc_cash_balance,
    calc_ending_nav,
    calc_position_market_value_with_warnings,
)
from sino_account.performance.data.collect_snapshot import collect_snapshot
from sino_account.performance.data.contracts import build_code_units
from sino_account.performance.session import ensure_performance_session


def diagnose_snapshot_nav(account: Any | None = None) -> dict[str, Any]:
    ensure_performance_session()
    snapshot = collect_snapshot(account)
    positions = snapshot.get("positions") or []
    balance = snapshot.get("balance") or {}

    codes = sorted({str(p.get("code") or "") for p in positions if p.get("code")})
    from sino_account.core import session

    code_units = build_code_units(session.get_api(), codes) if codes else {}
    multipliers = build_code_multipliers(positions, [], code_units=code_units)

    rows: list[dict[str, Any]] = []
    for position in positions:
        code = str(position.get("code") or "")
        shares = position_to_shares(position, multipliers)
        value, warning = position_market_value(position, multipliers)
        rows.append(
            {
                "code": code,
                "shares": shares,
                "quantity": position.get("quantity"),
                "unit": position.get("unit"),
                "price": position.get("price"),
                "last_price": position.get("last_price"),
                "pnl": position.get("pnl"),
                "market_value": value,
                "warning": warning,
            }
        )

    cash = calc_cash_balance(balance)
    market_value, warnings = calc_position_market_value_with_warnings(
        positions,
        multipliers=multipliers,
    )
    nav = calc_ending_nav(cash, market_value)

    return {
        "acc_balance": cash,
        "position_count_common": snapshot.get("position_count_common", 0),
        "position_count_share": snapshot.get("position_count_share", 0),
        "position_count_total": len(positions),
        "snapshot_market_value": market_value,
        "snapshot_nav": nav,
        "positions": rows,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Print snapshot NAV diagnostic breakdown.")
    args = parser.parse_args()
    del args

    try:
        report = diagnose_snapshot_nav()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("=== Snapshot NAV Diagnose ===")
    print(f"acc_balance:        {report['acc_balance']:,.2f}")
    print(
        f"positions:          common={report['position_count_common']} "
        f"share={report['position_count_share']} "
        f"total={report['position_count_total']}"
    )
    print(f"snapshot_market:    {report['snapshot_market_value']:,.2f}")
    print(f"snapshot_nav:       {report['snapshot_nav']:,.2f}")
    print()
    print(f"{'code':<8} {'shares':>10} {'price':>10} {'last':>10} {'pnl':>12} {'market':>14}")
    for row in report["positions"]:
        print(
            f"{row['code']:<8} {row['shares']:>10.0f} "
            f"{float(row['price'] or 0):>10.2f} {float(row['last_price'] or 0):>10.2f} "
            f"{float(row['pnl'] or 0):>12.2f} {row['market_value']:>14.2f}"
        )
        if row.get("warning"):
            print(f"  ! {row['warning']}")

    if report["warnings"]:
        print("\nWarnings:")
        for warning in report["warnings"]:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()

"""Query Shioaji account portfolio information."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from shioaji.account import FutureAccount, StockAccount

from sino_account.core.serialize import account_info
from sino_account.functions.get_account_balance import get_account_balance
from sino_account.functions.get_account_info import get_account_info
from sino_account.functions.get_margin import get_margin
from sino_account.functions.get_positions import get_positions
from sino_account.functions.get_profit_loss import default_date_range, get_profit_loss
from sino_account.functions.get_settlements import get_settlements
from sino_account.functions.login import login, logout


QUERY_DELAY_SECONDS = 0.25


def _throttle() -> None:
    time.sleep(QUERY_DELAY_SECONDS)


def _query_stock_account(api: Any, account: StockAccount, begin: str, end: str) -> dict[str, Any]:
    result: dict[str, Any] = {"account": account_info(account)}
    result["balance"] = get_account_balance(account)
    _throttle()
    result["positions"] = get_positions(account)
    _throttle()
    result["profit_loss"] = get_profit_loss(account, begin, end)
    _throttle()
    result["settlements"] = get_settlements(account)
    _throttle()
    return result


def _query_future_account(api: Any, account: FutureAccount, begin: str, end: str) -> dict[str, Any]:
    result: dict[str, Any] = {"account": account_info(account)}
    result["margin"] = get_margin(account)
    _throttle()
    result["positions"] = get_positions(account)
    _throttle()
    result["profit_loss"] = get_profit_loss(account, begin, end)
    _throttle()
    return result


def query_portfolio(begin: str | None = None, end: str | None = None) -> dict[str, Any]:
    if begin is None or end is None:
        default_begin, default_end = default_date_range()
        begin = begin or default_begin
        end = end or default_end

    login_info = login()
    try:
        accounts_info = get_account_info()
        output: dict[str, Any] = {
            "environment": login_info.get("environment"),
            "query_period": {"begin": begin, "end": end},
            "accounts": accounts_info,
            "stock": [],
            "futures": [],
        }

        from sino_account.core import session

        api = session.get_api()
        for account in api.list_accounts():
            if isinstance(account, StockAccount):
                output["stock"].append(_query_stock_account(api, account, begin, end))
            elif isinstance(account, FutureAccount):
                output["futures"].append(_query_future_account(api, account, begin, end))

        return output
    finally:
        logout()


def main() -> None:
    parser = argparse.ArgumentParser(description="Query Shioaji account portfolio information.")
    parser.add_argument("--begin", help="Profit/loss start date (YYYY-MM-DD). Default: first day of current month.")
    parser.add_argument("--end", help="Profit/loss end date (YYYY-MM-DD). Default: today.")
    args = parser.parse_args()

    try:
        result = query_portfolio(begin=args.begin, end=args.end)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

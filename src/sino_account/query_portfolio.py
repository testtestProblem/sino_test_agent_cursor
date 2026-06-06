"""Query Shioaji account portfolio information."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any

import shioaji as sj
from dotenv import load_dotenv
from shioaji.account import FutureAccount, StockAccount


QUERY_DELAY_SECONDS = 0.25


def _serialize(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _serialize(value) for key, value in obj.items()}
    if hasattr(obj, "dict") and callable(obj.dict):
        return _serialize(obj.dict())
    if is_dataclass(obj):
        return _serialize(asdict(obj))
    if hasattr(obj, "__dict__"):
        return _serialize(vars(obj))
    return str(obj)


def _account_info(account: Any) -> dict[str, Any]:
    account_type = getattr(account, "account_type", None)
    if account_type is None:
        if isinstance(account, StockAccount):
            account_type = "S"
        elif isinstance(account, FutureAccount):
            account_type = "F"
        else:
            account_type = type(account).__name__[0]

    return {
        "account_type": account_type,
        "person_id": getattr(account, "person_id", ""),
        "broker_id": getattr(account, "broker_id", ""),
        "account_id": getattr(account, "account_id", ""),
        "signed": getattr(account, "signed", None),
        "username": getattr(account, "username", ""),
    }


def _default_date_range() -> tuple[str, str]:
    today = date.today()
    begin = today.replace(day=1).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    return begin, end


def _throttle() -> None:
    time.sleep(QUERY_DELAY_SECONDS)


def _login(api: sj.Shioaji) -> None:
    api_key = os.environ.get("SJ_API_KEY")
    secret_key = os.environ.get("SJ_SEC_KEY")
    if not api_key or not secret_key:
        raise SystemExit(
            "Missing SJ_API_KEY or SJ_SEC_KEY. Copy .env.example to .env and fill in your credentials."
        )

    api.login(
        api_key=api_key,
        secret_key=secret_key,
        fetch_contract=False,
        subscribe_trade=False,
    )

    ca_path = os.environ.get("SJ_CA_PATH")
    ca_passwd = os.environ.get("SJ_CA_PASSWD")
    if ca_path and ca_passwd:
        api.activate_ca(ca_path=ca_path, ca_passwd=ca_passwd)


def _query_stock_account(api: sj.Shioaji, account: StockAccount, begin: str, end: str) -> dict[str, Any]:
    result: dict[str, Any] = {"account": _account_info(account)}

    result["balance"] = _serialize(api.account_balance(account=account))
    _throttle()

    result["positions"] = _serialize(api.list_positions(account=account))
    _throttle()

    result["profit_loss"] = _serialize(api.list_profit_loss(account, begin, end))
    _throttle()

    result["settlements"] = _serialize(api.settlements(account=account))
    _throttle()

    return result


def _query_future_account(api: sj.Shioaji, account: FutureAccount, begin: str, end: str) -> dict[str, Any]:
    result: dict[str, Any] = {"account": _account_info(account)}

    result["margin"] = _serialize(api.margin(account=account))
    _throttle()

    result["positions"] = _serialize(api.list_positions(account=account))
    _throttle()

    result["profit_loss"] = _serialize(api.list_profit_loss(account, begin, end))
    _throttle()

    return result


def query_portfolio(begin: str | None = None, end: str | None = None) -> dict[str, Any]:
    load_dotenv()

    if begin is None or end is None:
        default_begin, default_end = _default_date_range()
        begin = begin or default_begin
        end = end or default_end

    production = os.environ.get("SJ_PRODUCTION", "false").lower() == "true"
    api = sj.Shioaji(simulation=not production)

    try:
        _login(api)

        accounts = api.list_accounts()
        output: dict[str, Any] = {
            "environment": "production" if production else "simulation",
            "query_period": {"begin": begin, "end": end},
            "accounts": [_account_info(account) for account in accounts],
            "stock": [],
            "futures": [],
        }

        for account in accounts:
            if isinstance(account, StockAccount):
                output["stock"].append(_query_stock_account(api, account, begin, end))
            elif isinstance(account, FutureAccount):
                output["futures"].append(_query_future_account(api, account, begin, end))

        return output
    finally:
        api.logout()


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

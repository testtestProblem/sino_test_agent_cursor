"""Collect account balance and positions snapshot."""

from __future__ import annotations

from typing import Any

from sino_account.core import session
from sino_account.core.serialize import resolve_account, serialize
from sino_account.performance.accounts import ensure_stock_account
from sino_account.performance.data.throttle import throttle


def collect_snapshot(account: Any | None = None) -> dict[str, Any]:
    api = session.get_api()
    target = resolve_account(api, account)
    ensure_stock_account(target)

    balance = serialize(api.account_balance(account=target))
    throttle()
    positions = serialize(api.list_positions(account=target))

    return {
        "balance": balance,
        "positions": positions,
    }

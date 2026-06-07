"""Fetch realized profit/loss trades over a date range in monthly chunks."""

from __future__ import annotations

from typing import Any

from sino_account.core import session
from sino_account.core.serialize import resolve_account, serialize
from sino_account.performance.accounts import ensure_stock_account
from sino_account.performance.data.throttle import throttle
from sino_account.performance.date_range import monthly_chunks


def get_profit_loss_range(
    account: Any | None,
    start: str,
    end: str,
) -> list[Any]:
    api = session.get_api()
    target = resolve_account(api, account)
    ensure_stock_account(target)

    all_trades: list[Any] = []
    for chunk_start, chunk_end in monthly_chunks(start, end):
        trades = api.list_profit_loss(target, chunk_start, chunk_end)
        all_trades.extend(serialize(trades))
        throttle()

    return all_trades

"""Fetch realized profit/loss summary grouped by stock."""

from __future__ import annotations

from typing import Any

from sino_account.core import session
from sino_account.core.serialize import resolve_account, serialize
from sino_account.performance.accounts import ensure_stock_account


def get_profit_loss_summary(
    account: Any | None,
    start: str,
    end: str,
) -> dict[str, Any]:
    api = session.get_api()
    target = resolve_account(api, account)
    ensure_stock_account(target)

    result = api.list_profit_loss_summary(target, start, end)
    return serialize(result)

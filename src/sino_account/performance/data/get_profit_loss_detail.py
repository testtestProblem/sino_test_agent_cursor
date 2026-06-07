"""Fetch profit/loss detail for a specific position id."""

from __future__ import annotations

from typing import Any

from sino_account.core import session
from sino_account.core.serialize import resolve_account, serialize
from sino_account.performance.accounts import ensure_stock_account


def get_profit_loss_detail(
    account: Any | None,
    detail_id: int,
) -> list[Any]:
    api = session.get_api()
    target = resolve_account(api, account)
    ensure_stock_account(target)

    details = api.list_profit_loss_detail(target, detail_id=detail_id)
    return serialize(details)

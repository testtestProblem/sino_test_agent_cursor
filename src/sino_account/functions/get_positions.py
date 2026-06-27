"""Query account positions."""

from __future__ import annotations

from typing import Any

from shioaji.constant import Unit

from sino_account.core import session
from sino_account.core.serialize import resolve_stock_account, serialize


def get_positions(account: Any | None = None) -> list[Any]:
    """Return stock positions via Share unit (quantity is shares; includes whole lots)."""
    api = session.get_api()
    target = resolve_stock_account(api, account)
    return serialize(api.list_positions(account=target, unit=Unit.Share))

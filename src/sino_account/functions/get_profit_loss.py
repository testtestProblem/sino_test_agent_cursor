"""Query realized profit and loss."""

from __future__ import annotations

from datetime import date
from typing import Any

from sino_account.core import session
from sino_account.core.serialize import resolve_account, serialize


def default_date_range() -> tuple[str, str]:
    today = date.today()
    begin = today.replace(day=1).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    return begin, end


def get_profit_loss(
    account: Any | None = None,
    begin: str | None = None,
    end: str | None = None,
) -> list[Any]:
    api = session.get_api()
    target = resolve_account(api, account)

    if begin is None or end is None:
        default_begin, default_end = default_date_range()
        begin = begin or default_begin
        end = end or default_end

    return serialize(api.list_profit_loss(target, begin, end))

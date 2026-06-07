"""Query stock account balance."""

from __future__ import annotations

from typing import Any

from sino_account.core import session
from sino_account.core.serialize import resolve_account, serialize


def get_account_balance(account: Any | None = None) -> dict[str, Any]:
    api = session.get_api()
    target = resolve_account(api, account)
    return serialize(api.account_balance(account=target))

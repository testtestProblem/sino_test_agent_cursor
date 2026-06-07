"""Query futures account margin."""

from __future__ import annotations

from typing import Any

from sino_account.core import session
from sino_account.core.serialize import resolve_account, serialize


def get_margin(account: Any | None = None) -> dict[str, Any]:
    api = session.get_api()
    target = resolve_account(api, account)
    return serialize(api.margin(account=target))

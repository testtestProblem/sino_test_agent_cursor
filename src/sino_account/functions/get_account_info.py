"""List Shioaji accounts."""

from __future__ import annotations

from typing import Any

from sino_account.core import session
from sino_account.core.serialize import account_info


def get_account_info() -> list[dict[str, Any]]:
    api = session.get_api()
    accounts = api.list_accounts()
    return [account_info(account) for account in accounts]

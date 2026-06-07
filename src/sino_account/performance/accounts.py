"""Account validation helpers for performance features."""

from __future__ import annotations

from typing import Any

from sino_account.core.serialize import _account_type_code, account_info


def ensure_stock_account(account: Any) -> None:
    if _account_type_code(account) != "S":
        info = account_info(account)
        raise ValueError(
            f"僅支援證券帳戶 (S)，目前帳戶類型為 {info.get('account_type')}"
        )

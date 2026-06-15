"""Serialization helpers for Shioaji API responses."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

import shioaji as sj
from shioaji.account import FutureAccount, StockAccount


def _shioaji_builtin_value(obj: Any) -> Any | None:
    """Convert Shioaji builtins enum (AccountType, FetchStatus, ...) to JSON-safe value."""
    obj_type = type(obj)
    if obj_type.__module__ != "builtins":
        return None
    if not hasattr(obj, "value"):
        return None
    return obj.value


def serialize(obj: Any) -> Any:
    builtin_value = _shioaji_builtin_value(obj)
    if builtin_value is not None:
        return serialize(builtin_value)

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {str(key): serialize(value) for key, value in obj.items()}

    if hasattr(obj, "dict") and callable(obj.dict):
        return serialize(obj.dict())
    if is_dataclass(obj):
        return serialize(asdict(obj))
    if hasattr(obj, "__dict__"):
        return serialize(vars(obj))
    return str(obj)


def _account_type_code(account: Any) -> str:
    account_type = getattr(account, "account_type", None)
    if account_type is None:
        if isinstance(account, StockAccount):
            return "S"
        if isinstance(account, FutureAccount):
            return "F"
        return type(account).__name__[0]

    value = getattr(account_type, "value", None)
    if isinstance(value, str):
        return value

    return str(account_type)


def account_info(account: Any) -> dict[str, Any]:
    return {
        "account_type": _account_type_code(account),
        "person_id": getattr(account, "person_id", ""),
        "broker_id": getattr(account, "broker_id", ""),
        "account_id": getattr(account, "account_id", ""),
        "signed": getattr(account, "signed", None),
        "username": getattr(account, "username", ""),
    }


def account_label(account: Any) -> str:
    info = account_info(account)
    return f"{info['account_type']} | {info['broker_id']}-{info['account_id']}"


def extract_acc_balance(balance: Any) -> float:
    """Read acc_balance from AccountBalance (MappingMixin), dict, or list wrapper."""
    if balance is None:
        return 0.0

    if isinstance(balance, (list, tuple)):
        for item in balance:
            value = extract_acc_balance(item)
            if value != 0.0:
                return value
        if balance:
            return extract_acc_balance(balance[0])
        return 0.0

    if isinstance(balance, dict):
        for key in ("acc_balance", "AccBalance"):
            value = balance.get(key)
            if value is not None and value != "":
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return 0.0

    if hasattr(balance, "dict") and callable(balance.dict):
        try:
            return extract_acc_balance(balance.dict())
        except Exception:
            pass

    for key in ("acc_balance", "AccBalance"):
        if hasattr(balance, "__getitem__"):
            try:
                value = balance[key]
                if value is not None and value != "":
                    return float(value)
            except (KeyError, TypeError, ValueError):
                continue

    if hasattr(balance, "acc_balance"):
        try:
            value = getattr(balance, "acc_balance", None)
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            pass

    return 0.0


def resolve_stock_account(api: sj.Shioaji, account: Any | None) -> Any:
    """Return a stock account for portfolio queries."""
    if account is not None:
        if _account_type_code(account) != "S":
            raise ValueError(
                "此查詢僅支援證券帳戶 (S)，"
                f"目前選擇: {_account_type_code(account)} | "
                f"{getattr(account, 'broker_id', '')}-{getattr(account, 'account_id', '')}"
            )
        return account

    stock_account = getattr(api, "stock_account", None)
    if stock_account is not None:
        return stock_account

    for item in api.list_accounts():
        if _account_type_code(item) == "S":
            return item

    raise RuntimeError("找不到證券帳戶 (stock_account)")


def resolve_account(api: sj.Shioaji, account: Any | None) -> Any:
    if account is not None:
        return account

    stock_account = getattr(api, "stock_account", None)
    if stock_account is not None:
        return stock_account

    futopt_account = getattr(api, "futopt_account", None)
    if futopt_account is not None:
        return futopt_account

    accounts = api.list_accounts()
    if not accounts:
        raise RuntimeError("找不到可用帳戶")

    return accounts[0]

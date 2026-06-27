"""Query stock account trading limits (交易額度)."""

from __future__ import annotations

from typing import Any

from sino_account.core import session
from sino_account.core.serialize import resolve_stock_account, serialize

_LIMIT_FIELDS = (
    ("trading_limit", "電子交易總額度"),
    ("trading_used", "電子交易已用額度"),
    ("trading_available", "電子交易可用額度"),
    ("margin_limit", "融資額度上限"),
    ("margin_used", "融資已用額度"),
    ("margin_available", "融資可用額度"),
    ("short_limit", "融券額度上限"),
    ("short_used", "融券已用額度"),
    ("short_available", "融券可用額度"),
)


def _read_limit_int(raw: Any, key: str, serialized: dict[str, Any]) -> int:
    if hasattr(raw, key):
        try:
            value = getattr(raw, key)
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            pass

    if hasattr(raw, "__getitem__"):
        try:
            value = raw[key]
            if value is not None:
                return int(value)
        except (KeyError, TypeError, ValueError):
            pass

    if hasattr(raw, "dict") and callable(raw.dict):
        try:
            value = raw.dict().get(key)
            if value is not None:
                return int(value)
        except Exception:
            pass

    try:
        return int(serialized.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def get_trading_limits(account: Any | None = None) -> dict[str, Any]:
    """Return trading / margin / short selling limits for a stock account."""
    api = session.get_api()
    target = resolve_stock_account(api, account)
    raw = api.trading_limits(account=target)
    serialized = serialize(raw)
    data = serialized if isinstance(serialized, dict) else {}

    result = dict(data)
    for key, _ in _LIMIT_FIELDS:
        result[key] = _read_limit_int(raw, key, data)

    if all(int(result.get(key) or 0) == 0 for key, _ in _LIMIT_FIELDS):
        result["warning"] = (
            "所有額度為 0；請確認已 Login、選擇證券帳戶，且於交易日 8:30~15:00 查詢。"
            f" serialize={serialized!r}"
        )

    return result


def format_trading_limits_report(data: dict[str, Any]) -> str:
    """Format trading limits as readable text."""
    lines = ["=== 交易額度 ==="]
    for key, label in _LIMIT_FIELDS:
        value = int(data.get(key) or 0)
        lines.append(f"{label:<16} {value:>14,}")

    warning = str(data.get("warning") or "").strip()
    if warning:
        lines.append("")
        lines.append(f"提示: {warning}")

    lines.append("")
    lines.append("（查詢時間：交易日 8:30~15:00；僅證券帳戶）")
    return "\n".join(lines)

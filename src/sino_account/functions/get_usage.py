"""Query API traffic and connection usage."""

from __future__ import annotations

from typing import Any

from sino_account.core import session
from sino_account.core.serialize import serialize

_BYTES_PER_MB = 1024 * 1024
_BYTES_PER_GB = 1024 * 1024 * 1024
_USAGE_FIELDS = ("connections", "bytes", "limit_bytes", "remaining_bytes")


def _bytes_to_mb(value: int) -> float:
    return round(value / _BYTES_PER_MB, 2)


def _bytes_to_gb(value: int) -> float:
    return round(value / _BYTES_PER_GB, 2)


def _read_usage_int(raw: Any, key: str, serialized: dict[str, Any]) -> int:
    """Read a numeric UsageOut field; Shioaji UsageOut has no .dict()."""
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


def get_usage() -> dict[str, Any]:
    """Return daily API usage: connections, bytes used, limit, remaining."""
    api = session.get_api()
    raw = api.usage()
    serialized = serialize(raw)
    data = serialized if isinstance(serialized, dict) else {}

    connections = _read_usage_int(raw, "connections", data)
    bytes_used = _read_usage_int(raw, "bytes", data)
    limit_bytes = _read_usage_int(raw, "limit_bytes", data)
    remaining_bytes = _read_usage_int(raw, "remaining_bytes", data)

    result = dict(data)
    result["connections"] = connections
    result["bytes"] = bytes_used
    result["limit_bytes"] = limit_bytes
    result["remaining_bytes"] = remaining_bytes
    result["bytes_mb"] = _bytes_to_mb(bytes_used)
    result["limit_mb"] = _bytes_to_mb(limit_bytes)
    result["limit_gb"] = _bytes_to_gb(limit_bytes)
    result["remaining_mb"] = _bytes_to_mb(remaining_bytes)
    result["remaining_gb"] = _bytes_to_gb(remaining_bytes)
    if limit_bytes > 0:
        result["used_percent"] = round(bytes_used / limit_bytes * 100, 2)

    if limit_bytes == 0 and connections == 0 and bytes_used == 0:
        result["warning"] = (
            "無法讀取 usage 數值；請確認已 Login 且 API 回傳正常。"
            f" serialize={serialized!r}"
        )

    return result


def format_usage_report(data: dict[str, Any]) -> str:
    """Format usage data as readable text."""
    connections = int(data.get("connections") or 0)
    bytes_mb = float(data.get("bytes_mb") or 0)
    limit_gb = float(data.get("limit_gb") or 0)
    remaining_gb = float(data.get("remaining_gb") or 0)
    used_percent = data.get("used_percent")

    lines = [
        "=== API 流量及連線數 ===",
        f"連線數:     {connections}",
        f"已用流量:   {bytes_mb:,.2f} MB / {limit_gb:,.2f} GB",
        f"剩餘流量:   {remaining_gb:,.2f} GB",
    ]
    if used_percent is not None:
        lines.append(f"使用率:     {float(used_percent):.2f}%")

    warning = str(data.get("warning") or "").strip()
    if warning:
        lines.append("")
        lines.append(f"提示: {warning}")

    lines.append("")
    lines.append("（每日 08:00 重置；詳見官方流量分級說明）")
    return "\n".join(lines)

"""Stock contract resolution for kbars queries."""

from __future__ import annotations

from typing import Any

import shioaji as sj


def ensure_contracts_loaded(api: sj.Shioaji) -> None:
    contracts = getattr(api, "Contracts", None)
    if contracts is None:
        raise RuntimeError(
            "商品檔未載入。績效查詢需使用 fetch_contract=True 登入。"
        )


def _lookup_contract(container: Any, code: str) -> Any | None:
    """Shioaji Contracts 不支援可靠的 `in` 判斷，需直接嘗試取值。"""
    if container is None:
        return None
    try:
        return container[code]
    except (KeyError, TypeError):
        return None


def resolve_stock_contract(api: sj.Shioaji, code: str) -> Any:
    ensure_contracts_loaded(api)
    stocks = api.Contracts.Stocks

    hit = _lookup_contract(stocks, code)
    if hit is not None:
        return hit

    for exchange in ("TSE", "OTC", "OES"):
        bucket = getattr(stocks, exchange, None)
        hit = _lookup_contract(bucket, code)
        if hit is not None:
            return hit

    raise KeyError(f"找不到股票商品檔: {code}")


def resolve_benchmark_contract(api: sj.Shioaji) -> Any:
    ensure_contracts_loaded(api)
    indexs = api.Contracts.Indexs

    hit = _lookup_contract(indexs, "001")
    if hit is not None:
        return hit

    tse = getattr(indexs, "TSE", None)
    hit = _lookup_contract(tse, "001")
    if hit is not None:
        return hit

    tse001 = getattr(tse, "TSE001", None) if tse is not None else None
    if tse001 is not None:
        return tse001

    raise KeyError("找不到加權指數商品檔 (001)")

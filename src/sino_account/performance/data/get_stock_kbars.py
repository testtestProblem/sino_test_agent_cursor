"""Fetch stock daily kbars with local file cache."""

from __future__ import annotations

import json
from typing import Any

from sino_account.core import session
from sino_account.core.serialize import serialize
from sino_account.performance.data.contracts import resolve_stock_contract
from sino_account.performance.data.throttle import throttle
from sino_account.performance.paths import kbars_cache_dir


def _cache_path(code: str, start: str, end: str):
    return kbars_cache_dir() / f"{code}_{start}_{end}.json"


def get_stock_kbars(code: str, start: str, end: str) -> dict[str, Any]:
    cache_file = _cache_path(code, start, end)
    if cache_file.exists():
        with cache_file.open(encoding="utf-8") as handle:
            return json.load(handle)

    api = session.get_api()
    contract = resolve_stock_contract(api, code)
    kbars = api.kbars(contract=contract, start=start, end=end)
    throttle()
    payload = serialize(kbars)

    with cache_file.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)

    return payload


def get_stock_kbars_batch(codes: list[str], start: str, end: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for code in sorted(set(codes)):
        try:
            results[code] = get_stock_kbars(code, start, end)
        except Exception as exc:
            errors[code] = str(exc)

    return {"kbars": results, "errors": errors}

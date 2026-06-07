"""Fetch TAIEX benchmark index kbars with local file cache."""

from __future__ import annotations

import json
from typing import Any

from sino_account.core import session
from sino_account.core.serialize import serialize
from sino_account.performance.data.contracts import resolve_benchmark_contract
from sino_account.performance.data.throttle import throttle
from sino_account.performance.paths import kbars_cache_dir

BENCHMARK_CODE = "001"


def get_benchmark_kbars(start: str, end: str) -> dict[str, Any]:
    cache_file = kbars_cache_dir() / f"INDEX_{BENCHMARK_CODE}_{start}_{end}.json"
    if cache_file.exists():
        with cache_file.open(encoding="utf-8") as handle:
            return json.load(handle)

    api = session.get_api()
    contract = resolve_benchmark_contract(api)
    kbars = api.kbars(contract=contract, start=start, end=end)
    throttle()
    payload = serialize(kbars)

    with cache_file.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)

    return payload

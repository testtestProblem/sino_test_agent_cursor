"""Collect account balance and positions snapshot."""



from __future__ import annotations



from typing import Any



from shioaji.constant import Unit



from sino_account.core import session

from sino_account.core.serialize import resolve_account, serialize

from sino_account.performance.accounts import ensure_stock_account

from sino_account.performance.data.throttle import throttle





def _merge_positions(

    common_positions: list[Any],

    share_positions: list[Any],

) -> list[Any]:

    merged: list[Any] = []

    for item in common_positions:

        payload = serialize(item)

        if isinstance(payload, dict):

            payload.setdefault("unit", "Common")

        merged.append(payload)



    for item in share_positions:

        payload = serialize(item)

        if isinstance(payload, dict):

            payload["unit"] = "Share"

        merged.append(payload)



    return merged





def collect_snapshot(account: Any | None = None) -> dict[str, Any]:

    api = session.get_api()

    target = resolve_account(api, account)

    ensure_stock_account(target)



    balance = serialize(api.account_balance(account=target))

    throttle()

    common_positions = api.list_positions(account=target)

    throttle()

    share_positions = api.list_positions(account=target, unit=Unit.Share)

    positions = _merge_positions(common_positions, share_positions)



    return {

        "balance": balance,

        "positions": positions,

        "position_count_common": len(common_positions),

        "position_count_share": len(share_positions),

    }



"""Login and logout helpers."""

from __future__ import annotations

import os
from typing import Any

from sino_account.core import session


def _contracts_ready(api: object) -> bool:
    contracts = getattr(api, "Contracts", None)
    if contracts is None:
        return False
    try:
        contracts.Stocks["2330"]
        return True
    except Exception:
        return False


def login(*, fetch_contract: bool = False) -> dict[str, Any]:
    if session.is_logged_in():
        api = session.get_api()
        if fetch_contract and not _contracts_ready(api):
            api.logout()
            session.clear_api()
        else:
            return {
                "status": "already_logged_in",
                "environment": session.get_environment(),
                "fetch_contract": fetch_contract,
            }

    session.load_env()
    production = os.environ.get("SJ_PRODUCTION", "false").lower() == "true"
    environment = "production" if production else "simulation"

    api = session.create_api()
    session.perform_login(api, fetch_contract=fetch_contract)
    session.set_api(api, environment)

    return {
        "status": "logged_in",
        "environment": environment,
        "fetch_contract": fetch_contract,
    }


def logout() -> dict[str, Any]:
    if not session.is_logged_in():
        return {"status": "not_logged_in"}

    api = session.get_api()
    api.logout()
    session.clear_api()

    return {"status": "logged_out"}

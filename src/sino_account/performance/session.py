"""Login helpers for performance queries."""

from __future__ import annotations

import os
from typing import Any

from sino_account.core import session


def _contracts_ready(api: Any) -> bool:
    contracts = getattr(api, "Contracts", None)
    if contracts is None:
        return False
    try:
        contracts.Stocks["2330"]
        contracts.Indexs.TSE.TSE001
        return True
    except Exception:
        return False


def login_for_performance() -> dict[str, Any]:
    if session.is_logged_in():
        api = session.get_api()
        api.logout()
        session.clear_api()

    session.load_env()
    production = os.environ.get("SJ_PRODUCTION", "false").lower() == "true"
    environment = "production" if production else "simulation"

    api = session.create_api()
    session.perform_login(api, fetch_contract=True)
    session.set_api(api, environment)

    return {"status": "logged_in", "environment": environment, "fetch_contract": True}


def ensure_performance_session() -> dict[str, Any]:
    if session.is_logged_in() and _contracts_ready(session.get_api()):
        return {"status": "ready", "fetch_contract": True}
    return login_for_performance()


def logout_performance() -> dict[str, Any]:
    if not session.is_logged_in():
        return {"status": "not_logged_in"}

    api = session.get_api()
    api.logout()
    session.clear_api()
    return {"status": "logged_out"}

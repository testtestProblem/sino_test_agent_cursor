"""Login and logout helpers."""

from __future__ import annotations

import os
from typing import Any

from sino_account.core import session


def login() -> dict[str, Any]:
    if session.is_logged_in():
        return {
            "status": "already_logged_in",
            "environment": session.get_environment(),
        }

    session.load_env()
    production = os.environ.get("SJ_PRODUCTION", "false").lower() == "true"
    environment = "production" if production else "simulation"

    api = session.create_api()
    session.perform_login(api)
    session.set_api(api, environment)

    return {
        "status": "logged_in",
        "environment": environment,
    }


def logout() -> dict[str, Any]:
    if not session.is_logged_in():
        return {"status": "not_logged_in"}

    api = session.get_api()
    api.logout()
    session.clear_api()

    return {"status": "logged_out"}

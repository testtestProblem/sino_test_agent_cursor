"""Shared Shioaji API session management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import shioaji as sj
from dotenv import load_dotenv

_api: sj.Shioaji | None = None
_environment: str = "unknown"


def is_logged_in() -> bool:
    return _api is not None


def get_environment() -> str:
    return _environment


def get_api() -> sj.Shioaji:
    if _api is None:
        raise RuntimeError("尚未登入，請先按 Login")
    return _api


def load_env() -> None:
    load_dotenv()
    project_root = Path(__file__).resolve().parents[3]
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)


def create_api() -> sj.Shioaji:
    load_env()
    production = os.environ.get("SJ_PRODUCTION", "false").lower() == "true"
    return sj.Shioaji(simulation=not production)


def set_api(api: sj.Shioaji, environment: str) -> None:
    global _api, _environment
    _api = api
    _environment = environment


def clear_api() -> None:
    global _api, _environment
    _api = None
    _environment = "unknown"


def perform_login(api: sj.Shioaji) -> None:
    load_env()
    api_key = os.environ.get("SJ_API_KEY")
    secret_key = os.environ.get("SJ_SEC_KEY")
    if not api_key or not secret_key:
        raise RuntimeError(
            "Missing SJ_API_KEY or SJ_SEC_KEY. Copy .env.example to .env and fill in your credentials."
        )

    api.login(
        api_key=api_key,
        secret_key=secret_key,
        fetch_contract=False,
        subscribe_trade=False,
    )

    ca_path = os.environ.get("SJ_CA_PATH")
    ca_passwd = os.environ.get("SJ_CA_PASSWD")
    if ca_path and ca_passwd:
        api.activate_ca(ca_path=ca_path, ca_passwd=ca_passwd)

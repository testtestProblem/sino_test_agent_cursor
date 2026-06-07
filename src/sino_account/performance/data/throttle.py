"""API rate-limit throttle for account queries."""

from __future__ import annotations

import time

QUERY_DELAY_SECONDS = 0.25


def throttle() -> None:
    time.sleep(QUERY_DELAY_SECONDS)

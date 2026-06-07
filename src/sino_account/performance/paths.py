"""Project path helpers for performance modules."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def kbars_cache_dir() -> Path:
    cache_dir = project_root() / "data" / "cache" / "kbars"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

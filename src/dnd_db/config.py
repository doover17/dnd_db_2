"""Configuration helpers for dnd_db."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DB_PATH = Path("data/sqlite/dnd_rules.db")
DB_PATH_ENV_VAR = "DND_DB_PATH"
API_BASE_URL_ENV_VAR = "DND_API_BASE_URL"
DEFAULT_API_BASE_URL = "https://www.dnd5eapi.co"


def get_db_path() -> str:
    """Return the absolute database path, honoring environment overrides."""
    env_value = os.getenv(DB_PATH_ENV_VAR)
    if env_value:
        return str(Path(env_value).expanduser().resolve())
    return str(DEFAULT_DB_PATH.resolve())


def get_api_base_url() -> str:
    """Return the SRD API base URL, honoring environment overrides."""
    env_value = os.getenv(API_BASE_URL_ENV_VAR)
    if env_value:
        return env_value.rstrip("/")
    return DEFAULT_API_BASE_URL.rstrip("/")

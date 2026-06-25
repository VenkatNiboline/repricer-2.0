"""Load credentials from ENV file (local) or process environment (Vercel)."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
ENV_FILE = ROOT / "ENV" / "AmazonCredentials.env"

_loaded = False

AMAZON_DISABLED_MESSAGE = (
    "Amazon SP-API access is disabled. Set AMAZON_API_ENABLED=true to re-enable."
)


class AmazonApiDisabledError(RuntimeError):
    """Raised when AMAZON_API_ENABLED is false."""


def load_env() -> None:
    global _loaded
    if _loaded:
        return
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    _loaded = True


def amazon_api_enabled() -> bool:
    load_env()
    raw = os.getenv("AMAZON_API_ENABLED", "true").strip().lower()
    return raw not in ("false", "0", "no", "off")


def assert_amazon_api_enabled() -> None:
    if not amazon_api_enabled():
        raise AmazonApiDisabledError(AMAZON_DISABLED_MESSAGE)

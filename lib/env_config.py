"""Load credentials from ENV file (local) or process environment (Vercel)."""

from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
ENV_FILE = ROOT / "ENV" / "AmazonCredentials.env"

_loaded = False


def load_env() -> None:
    global _loaded
    if _loaded:
        return
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    _loaded = True

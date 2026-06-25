"""Consistent API error handling — log details server-side, generic messages to clients."""

import logging
import sys
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from env_config import AmazonApiDisabledError  # noqa: E402

logger = logging.getLogger(__name__)


def raise_http_error(
    exc: Exception,
    *,
    status_code: int = 500,
    client_message: str = "An internal error occurred",
) -> None:
    """Log the real exception and raise a safe HTTP error for the client."""
    if isinstance(exc, AmazonApiDisabledError):
        raise HTTPException(503, str(exc)) from exc
    logger.exception(client_message)
    raise HTTPException(status_code, client_message) from exc

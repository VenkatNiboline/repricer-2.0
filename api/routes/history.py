"""Price history API."""

import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from api.auth import get_access_token, optional_user_id
from api.errors import raise_http_error
from price_reflection import verify_pending_reflections
from supabase_store import is_configured, is_readable, list_price_history

router = APIRouter()


def _validate_cron_secret(
    authorization: Optional[str],
    x_cron_secret: Optional[str],
) -> None:
    expected = os.getenv("CRON_SECRET", "")
    bearer = None
    if authorization and authorization.startswith("Bearer "):
        bearer = authorization.removeprefix("Bearer ").strip() or None
    secret = x_cron_secret or bearer
    if not expected or secret != expected:
        raise HTTPException(401, "Invalid cron secret")


@router.get("/history")
def get_history(
    country: Optional[str] = None,
    sku: Optional[str] = None,
    limit: int = 100,
    user_id: Optional[str] = Depends(optional_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    _ = user_id
    if not is_readable():
        return []
    try:
        return list_price_history(country=country, sku=sku, limit=limit, access_token=access_token)
    except Exception as exc:
        raise_http_error(exc, client_message="Failed to load history")


@router.get("/history/verify-pending-cron")
def verify_pending_cron(
    authorization: Optional[str] = Header(default=None),
    x_cron_secret: Optional[str] = Header(default=None),
):
    """Vercel cron: recheck pending reflections every minute."""
    _validate_cron_secret(authorization, x_cron_secret)
    from env_config import amazon_api_enabled

    if not amazon_api_enabled():
        return {"checked": 0, "reflected": 0, "results": [], "amazon_api_enabled": False}
    if not is_configured():
        raise HTTPException(
            503,
            "SUPABASE_SERVICE_ROLE_KEY required for scheduled reflection checks",
        )
    results = verify_pending_reflections()
    reflected = sum(1 for row in results if row.get("reflection_status") == "reflected")
    return {"checked": len(results), "reflected": reflected, "results": results}

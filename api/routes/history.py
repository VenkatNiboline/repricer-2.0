"""Price history API."""

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from api.auth import optional_user_id
from supabase_store import is_configured, list_price_history

router = APIRouter()


@router.get("/history")
def get_history(
    country: Optional[str] = None,
    sku: Optional[str] = None,
    limit: int = 100,
    user_id: Optional[str] = Depends(optional_user_id),
):
    _ = user_id
    if not is_configured():
        return []
    try:
        return list_price_history(country=country, sku=sku, limit=limit)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

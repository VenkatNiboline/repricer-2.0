"""SKU rules API."""

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from api.auth import AuthCtx, require_admin_auth, require_auth
from supabase_store import delete_sku_rule, is_configured, list_sku_rules, upsert_sku_rule

router = APIRouter()


class SkuRuleIn(BaseModel):
    sku: str
    country: str = "DE"
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    fbm_discount: Optional[float] = Field(default=None, ge=0, lt=1)
    sync_siblings: Optional[bool] = None
    sync_fbm: Optional[bool] = None
    notes: Optional[str] = None


class SkuRuleOut(SkuRuleIn):
    id: Optional[int] = None
    updated_at: Optional[str] = None


@router.get("/rules", response_model=list[SkuRuleOut])
def get_rules(
    country: Optional[str] = None,
    auth: AuthCtx = Depends(require_auth),
):
    if not is_configured():
        return []
    try:
        return list_sku_rules(country=country, access_token=auth.access_token)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.put("/rules", response_model=SkuRuleOut)
def save_rule(body: SkuRuleIn, auth: AuthCtx = Depends(require_admin_auth)):
    if not is_configured():
        raise HTTPException(503, "Supabase not configured")
    try:
        return upsert_sku_rule(
            body.model_dump(), updated_by=auth.user_id, access_token=auth.access_token
        )
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.delete("/rules/{sku}")
def remove_rule(sku: str, country: str = "DE", auth: AuthCtx = Depends(require_admin_auth)):
    if not is_configured():
        raise HTTPException(503, "Supabase not configured")
    try:
        delete_sku_rule(sku, country, access_token=auth.access_token)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

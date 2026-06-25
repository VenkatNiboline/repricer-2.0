"""App settings stored in Supabase."""

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from api.auth import get_access_token, optional_user_id, require_admin
from api.errors import raise_http_error
from supabase_store import get_app_settings, is_readable, is_configured, update_app_settings

router = APIRouter()


class AppSettingsOut(BaseModel):
    default_country: str
    default_region: str
    default_fbm_discount: float
    sync_siblings: bool
    sync_fbm: bool
    updated_at: Optional[str] = None


class AppSettingsIn(BaseModel):
    default_country: str = "DE"
    default_region: str = "EU"
    default_fbm_discount: float = Field(0.10, ge=0, lt=1)
    sync_siblings: bool = True
    sync_fbm: bool = True


@router.get("/app-settings", response_model=AppSettingsOut)
def read_settings(
    user_id: Optional[str] = Depends(optional_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    _ = user_id
    if not is_readable():
        return AppSettingsOut(
            default_country="DE",
            default_region="EU",
            default_fbm_discount=0.10,
            sync_siblings=True,
            sync_fbm=True,
        )
    try:
        return get_app_settings(access_token=access_token)
    except Exception as exc:
        raise_http_error(exc, client_message="Failed to load settings")


@router.put("/app-settings", response_model=AppSettingsOut)
def write_settings(body: AppSettingsIn, user_id: str = Depends(require_admin)):
    _ = user_id
    if not is_configured():
        raise HTTPException(503, "Supabase not configured")
    try:
        return update_app_settings(body.model_dump())
    except Exception as exc:
        raise_http_error(exc, client_message="Failed to save settings")

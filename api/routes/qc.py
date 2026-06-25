"""QC API routes."""

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from api.auth import get_access_token, optional_user_id, require_admin
from price_reflection import verify_history_row, verify_pending_reflections
from qc.runner import run_all_qc
from supabase_store import get_client, is_readable, is_configured, list_qc_findings, resolve_qc_finding

router = APIRouter()


class QcRunRequest(BaseModel):
    agents: Optional[list[str]] = None


@router.post("/qc/run")
def run_qc(body: QcRunRequest | None = None, user_id: Optional[str] = Depends(optional_user_id)):
    _ = user_id
    if not is_configured():
        raise HTTPException(503, "Supabase not configured")
    agents = body.agents if body else None
    return run_all_qc(agents)


@router.get("/qc/findings")
def get_findings(
    resolved: Optional[bool] = False,
    severity: Optional[str] = None,
    limit: int = 100,
    user_id: Optional[str] = Depends(optional_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    _ = user_id
    if not is_readable():
        return []
    return list_qc_findings(resolved=resolved, severity=severity, limit=limit, access_token=access_token)


@router.patch("/qc/findings/{finding_id}")
def patch_finding(finding_id: int, user_id: Optional[str] = Depends(optional_user_id)):
    _ = user_id
    if not is_configured():
        raise HTTPException(503, "Supabase not configured")
    resolve_qc_finding(finding_id)
    return {"ok": True}


@router.post("/history/verify-pending")
def verify_pending(
    user_id: Optional[str] = Depends(optional_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    _ = user_id
    return verify_pending_reflections(access_token=access_token)


@router.post("/history/{history_id}/verify")
def verify_one(
    history_id: int,
    user_id: Optional[str] = Depends(optional_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    _ = user_id
    if not is_readable():
        raise HTTPException(503, "Supabase not configured")
    client = get_client(access_token)
    result = (
        client.table("price_history").select("*").eq("id", history_id).limit(1).execute()
    )
    rows = result.data or []
    if not rows:
        raise HTTPException(404, "History row not found")
    return verify_history_row(rows[0], access_token=access_token)

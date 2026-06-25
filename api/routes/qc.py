"""QC API routes."""

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from api.auth import AuthCtx, require_auth
from price_reflection import verify_history_row, verify_pending_reflections
from qc.runner import run_all_qc
from supabase_store import _client_for, is_configured, list_qc_findings, resolve_qc_finding

router = APIRouter()


class QcRunRequest(BaseModel):
    agents: Optional[list[str]] = None


@router.post("/qc/run")
def run_qc(body: QcRunRequest | None = None, auth: AuthCtx = Depends(require_auth)):
    if not is_configured():
        raise HTTPException(503, "Supabase not configured")
    agents = body.agents if body else None
    return run_all_qc(agents)


@router.get("/qc/findings")
def get_findings(
    resolved: Optional[bool] = False,
    severity: Optional[str] = None,
    limit: int = 100,
    auth: AuthCtx = Depends(require_auth),
):
    if not is_configured():
        return []
    return list_qc_findings(
        resolved=resolved, severity=severity, limit=limit, access_token=auth.access_token
    )


@router.patch("/qc/findings/{finding_id}")
def patch_finding(finding_id: int, auth: AuthCtx = Depends(require_auth)):
    if not is_configured():
        raise HTTPException(503, "Supabase not configured")
    resolve_qc_finding(finding_id, access_token=auth.access_token)
    return {"ok": True}


@router.post("/history/verify-pending")
def verify_pending(auth: AuthCtx = Depends(require_auth)):
    return verify_pending_reflections()


@router.post("/history/{history_id}/verify")
def verify_one(history_id: int, auth: AuthCtx = Depends(require_auth)):
    if not is_configured():
        raise HTTPException(503, "Supabase not configured")
    client = _client_for(auth.access_token)
    result = (
        client.table("price_history").select("*").eq("id", history_id).limit(1).execute()
    )
    rows = result.data or []
    if not rows:
        raise HTTPException(404, "History row not found")
    return verify_history_row(rows[0])

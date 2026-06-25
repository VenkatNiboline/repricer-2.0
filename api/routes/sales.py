"""Sales data API and ETL triggers."""

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from amazon_listing import MARKETPLACE_IDS
from amazon_reports import fetch_and_flatten_sales_report
from api.auth import get_access_token, optional_user_id, require_admin
from api.errors import raise_http_error
from features_engine import run_features_engine
from qc.runner import run_all_qc
from supabase_store import get_client, is_readable, is_configured, list_sales_daily, upsert_sales_rows

router = APIRouter()


class SalesSyncRequest(BaseModel):
    country: str = "DE"
    region: str = "EU"
    days: int = 7


class SalesSummary(BaseModel):
    country: str
    total_revenue_7d: float
    total_units_7d: int
    row_count: int


@router.get("/sales/summary", response_model=SalesSummary)
def sales_summary(
    country: str = Query("DE"),
    user_id: Optional[str] = Depends(optional_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    _ = user_id
    country = country.upper()
    rows = list_sales_daily(country=country, days=7, limit=5000, access_token=access_token)
    revenue = sum(float(r.get("ordered_product_sales_amount") or 0) for r in rows)
    units = sum(int(r.get("units_ordered") or 0) for r in rows)
    return SalesSummary(
        country=country,
        total_revenue_7d=round(revenue, 2),
        total_units_7d=units,
        row_count=len(rows),
    )


@router.get("/sales")
def get_sales(
    country: Optional[str] = Query(None),
    sku: Optional[str] = Query(None),
    days: int = Query(30),
    limit: int = Query(500),
    user_id: Optional[str] = Depends(optional_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    _ = user_id
    if not is_readable():
        return []
    return list_sales_daily(country=country, sku=sku, days=days, limit=limit, access_token=access_token)


def _run_sales_sync(country: str, region: str, days: int, created_by: Optional[str] = None) -> dict:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=max(1, days) - 1)
    client = get_client()
    run = (
        client.table("sales_sync_runs")
        .insert(
            {
                "country": country,
                "date_start": start.isoformat(),
                "date_end": end.isoformat(),
                "status": "running",
                "created_by": created_by,
            }
        )
        .execute()
    )
    run_id = (run.data or [{}])[0].get("id")
    try:
        rows = fetch_and_flatten_sales_report(country, start, end, region=region)
        count = upsert_sales_rows(rows)
        run_features_engine(country)
        run_all_qc(["data_qc", "pricing_qc"])
        client.table("sales_sync_runs").update(
            {
                "row_count": count,
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", run_id).execute()
        return {"ok": True, "country": country, "rows": count, "date_start": start, "date_end": end}
    except Exception as exc:
        client.table("sales_sync_runs").update(
            {"status": "failed", "error": str(exc)}
        ).eq("id", run_id).execute()
        raise


@router.post("/sales/sync-cron")
def sync_sales_cron(
    body: SalesSyncRequest,
    x_cron_secret: Optional[str] = Header(default=None),
):
    expected = os.getenv("CRON_SECRET", "")
    if not expected or x_cron_secret != expected:
        raise HTTPException(401, "Invalid cron secret")
    country = body.country.upper()
    if country not in MARKETPLACE_IDS:
        raise HTTPException(400, f"Unknown country: {country}")
    if not is_configured():
        raise HTTPException(503, "Supabase not configured")
    try:
        return _run_sales_sync(country, body.region, body.days)
    except Exception as exc:
        raise_http_error(exc, client_message="Sales sync failed")


@router.post("/sales/sync")
def sync_sales(body: SalesSyncRequest, user_id: str = Depends(require_admin)):
    country = body.country.upper()
    if country not in MARKETPLACE_IDS:
        raise HTTPException(400, f"Unknown country: {country}")
    if not is_configured():
        raise HTTPException(503, "Supabase not configured")
    try:
        return _run_sales_sync(country, body.region, body.days, created_by=user_id)
    except Exception as exc:
        raise_http_error(exc, client_message="Sales sync failed")

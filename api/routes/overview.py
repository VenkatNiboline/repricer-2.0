"""Batched overview KPIs."""

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from api.auth import AuthCtx, require_auth
from api.errors import raise_http_error
from catalog import catalog_stats, get_catalog_payload
from supabase_store import is_readable, list_qc_findings, list_sales_daily

router = APIRouter()


class OverviewResponse(BaseModel):
    country: str
    catalog_total: int
    catalog_fba: int
    catalog_fbm: int
    catalog_synced_at: Optional[str]
    sales_revenue_7d: float
    sales_units_7d: int
    open_qc_critical: int
    open_qc_warning: int
    open_qc_total: int


@router.get("/overview", response_model=OverviewResponse)
def get_overview(country: str = Query("DE"), auth: AuthCtx = Depends(require_auth)):
    country = country.upper()

    if not is_readable():
        return OverviewResponse(
            country=country,
            catalog_total=0,
            catalog_fba=0,
            catalog_fbm=0,
            catalog_synced_at=None,
            sales_revenue_7d=0,
            sales_units_7d=0,
            open_qc_critical=0,
            open_qc_warning=0,
            open_qc_total=0,
        )

    try:
        payload = get_catalog_payload(country, refresh=False, access_token=auth.access_token)
        stats = catalog_stats(payload)
        sales_rows = list_sales_daily(
            country=country, days=7, limit=5000, access_token=auth.access_token
        )
        revenue = sum(float(r.get("ordered_product_sales_amount") or 0) for r in sales_rows)
        units = sum(int(r.get("units_ordered") or 0) for r in sales_rows)

        critical = list_qc_findings(
            resolved=False, severity="critical", limit=500, access_token=auth.access_token
        )
        warning = list_qc_findings(
            resolved=False, severity="warning", limit=500, access_token=auth.access_token
        )
        all_open = list_qc_findings(resolved=False, limit=500, access_token=auth.access_token)

        return OverviewResponse(
            country=country,
            catalog_total=stats.get("total", 0),
            catalog_fba=stats.get("fba", 0),
            catalog_fbm=stats.get("fbm_suffix", 0),
            catalog_synced_at=stats.get("synced_at"),
            sales_revenue_7d=round(revenue, 2),
            sales_units_7d=units,
            open_qc_critical=len(critical),
            open_qc_warning=len(warning),
            open_qc_total=len(all_open),
        )
    except Exception as exc:
        raise_http_error(exc, client_message="Failed to load overview")

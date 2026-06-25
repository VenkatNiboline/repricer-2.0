"""QC agent for sales data integrity — full plan checks."""

import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from marketplaces import catalog_table_for_country, country_for_marketplace_id
from supabase_store import get_client, is_configured, insert_qc_findings


def _add(findings: List[Dict[str, Any]], qc_run_id: int, check_id: str, severity: str, message: str, **extra):
    findings.append(
        {
            "qc_run_id": qc_run_id,
            "agent_name": "data_qc",
            "check_id": check_id,
            "severity": severity,
            "message": message,
            **extra,
        }
    )


def run_data_qc(*, qc_run_id: int) -> List[Dict[str, Any]]:
    if not is_configured():
        return []

    findings: List[Dict[str, Any]] = []
    client = get_client()

    sales = (
        client.table("sales_daily")
        .select("*")
        .order("ob_date", desc=True)
        .limit(2000)
        .execute()
        .data
        or []
    )

    if not sales:
        _add(findings, qc_run_id, "no_sales_data", "info", "No sales data loaded yet")
        insert_qc_findings(findings)
        return findings

    latest_dates = [date.fromisoformat(str(r["ob_date"])) for r in sales if r.get("ob_date")]
    if latest_dates:
        latest_date = max(latest_dates)
        if latest_date < date.today() - timedelta(days=2):
            _add(
                findings,
                qc_run_id,
                "stale_data",
                "warning",
                f"Latest sales data is from {latest_date}, older than 2 days",
            )

    dup_keys = Counter(
        (r.get("ob_marketplace_id"), r.get("child_asin"), r.get("ob_date")) for r in sales
    )
    for key, count in dup_keys.items():
        if count > 1:
            _add(
                findings,
                qc_run_id,
                "duplicate_rows",
                "critical",
                f"Duplicate sales rows for {key[1]} on {key[2]} ({count} rows)",
                asin=str(key[1]),
            )

    catalog_asins: Dict[str, Dict[str, Any]] = {}
    for country in ("DE", "FR", "IT", "ES", "NL", "BE", "PL", "SE", "UK"):
        table = catalog_table_for_country(country)
        rows = client.table(table).select("asin, sku, currency").limit(5000).execute().data or []
        for row in rows:
            if row.get("asin"):
                catalog_asins[f"{country}:{row['asin']}"] = row

    for row in sales[:500]:
        asin = row.get("child_asin")
        mp = row.get("ob_marketplace_id")
        country = country_for_marketplace_id(mp) if mp else None
        if not asin or not country:
            continue
        cat = catalog_asins.get(f"{country}:{asin}")
        if not cat:
            _add(
                findings,
                qc_run_id,
                "missing_sku_mapping",
                "warning",
                f"Sales for ASIN {asin} ({country}) not in catalog",
                asin=asin,
                country=country,
            )
            continue
        sales_currency = row.get("ordered_product_sales_currency_code")
        catalog_currency = cat.get("currency")
        if sales_currency and catalog_currency and sales_currency != catalog_currency:
            _add(
                findings,
                qc_run_id,
                "currency_mismatch",
                "warning",
                f"Currency mismatch for {cat.get('sku')}: sales {sales_currency} vs catalog {catalog_currency}",
                sku=cat.get("sku"),
                country=country,
            )

        amount = row.get("ordered_product_sales_amount")
        units = row.get("units_ordered")
        if amount is not None and float(amount) < 0:
            _add(findings, qc_run_id, "negative_metrics", "critical", f"Negative sales amount for {asin}")
        if units is not None and int(units) < 0:
            _add(findings, qc_run_id, "negative_metrics", "critical", f"Negative units for {asin}")

        sessions = row.get("sessions") or 0
        if int(sessions) > 0 and amount is None and units is None:
            _add(
                findings,
                qc_run_id,
                "null_sales_with_traffic",
                "warning",
                f"Traffic without sales data for ASIN {asin}",
                asin=asin,
                country=country,
            )

    if findings:
        insert_qc_findings(findings)
    return findings

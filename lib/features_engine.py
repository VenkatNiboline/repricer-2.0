"""Compute pricing features from sales and history data."""

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config" / "pricing_features.yaml"

sys.path.insert(0, str(ROOT / "lib"))

from supabase_store import get_client, is_configured


def load_features_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"features": [], "signals": []}
    with open(CONFIG_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {"features": [], "signals": []}


def compute_features_for_sku(country: str, sku: str, days: int = 7) -> List[Dict[str, Any]]:
    if not is_configured():
        return []

    client = get_client()
    since = (date.today() - timedelta(days=days)).isoformat()
    sales = (
        client.table("sales_daily")
        .select("*")
        .eq("sku", sku)
        .gte("ob_date", since)
        .execute()
        .data
        or []
    )

    units = sum(int(r.get("units_ordered") or 0) for r in sales)
    revenue = sum(float(r.get("ordered_product_sales_amount") or 0) for r in sales)
    sessions = sum(int(r.get("sessions") or 0) for r in sales)
    buy_boxes = [float(r.get("buy_box_percentage") or 0) for r in sales if r.get("buy_box_percentage")]
    buy_box_avg = sum(buy_boxes) / len(buy_boxes) if buy_boxes else 0

    feature_date = date.today()
    computed: List[Dict[str, Any]] = [
        {
            "sku": sku,
            "country": country.upper(),
            "feature_date": feature_date.isoformat(),
            "feature_id": "units_7d",
            "feature_value": units,
        },
        {
            "sku": sku,
            "country": country.upper(),
            "feature_date": feature_date.isoformat(),
            "feature_id": "revenue_7d",
            "feature_value": revenue,
        },
        {
            "sku": sku,
            "country": country.upper(),
            "feature_date": feature_date.isoformat(),
            "feature_id": "buy_box_avg_7d",
            "feature_value": buy_box_avg,
        },
    ]

    signal_value = 1 if units >= 10 and buy_box_avg >= 90 and sessions > 0 else 0
    computed.append(
        {
            "sku": sku,
            "country": country.upper(),
            "feature_date": feature_date.isoformat(),
            "feature_id": "signal_underpriced_high_demand",
            "feature_value": signal_value,
            "metadata": {"units_7d": units, "buy_box_avg_7d": buy_box_avg, "sessions_7d": sessions},
        }
    )

    for row in computed:
        client.table("pricing_features_daily").upsert(
            row, on_conflict="sku,country,feature_date,feature_id"
        ).execute()

    return computed


def run_features_engine(country: str, limit: int = 100) -> int:
    if not is_configured():
        return 0
    client = get_client()
    from marketplaces import catalog_table_for_country

    table = catalog_table_for_country(country)
    catalog = client.table(table).select("sku").limit(limit).execute().data or []
    count = 0
    for row in catalog:
        sku = row.get("sku")
        if sku:
            compute_features_for_sku(country, sku)
            count += 1
    return count

"""Supabase persistence for catalog, rules, history, and settings."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
ENV_FILE = ROOT / "ENV" / "AmazonCredentials.env"

load_dotenv(ENV_FILE)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

_client = None


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def get_client():
    global _client
    if not is_configured():
        raise RuntimeError(
            "Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in ENV/AmazonCredentials.env"
        )
    if _client is None:
        from supabase import create_client

        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _client


def upsert_catalog_rows(country: str, rows: List[Dict[str, Any]]) -> int:
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()
    payload = []
    for row in rows:
        payload.append(
            {
                "sku": row["sku"],
                "country": country.upper(),
                "asin": row.get("asin"),
                "product_type": row.get("product_type"),
                "fulfillment": row.get("fulfillment", "UNKNOWN"),
                "price": row.get("price"),
                "currency": row.get("currency", "EUR"),
                "fba_pair": row.get("fba_pair"),
                "is_fbm": bool(row.get("is_fbm")),
                "parent_sku": row.get("parent_sku"),
                "size_label": row.get("size_label"),
                "units": row.get("units"),
                "synced_at": now,
            }
        )

    batch_size = 200
    for index in range(0, len(payload), batch_size):
        batch = payload[index : index + batch_size]
        client.table("sku_catalog").upsert(batch, on_conflict="sku,country").execute()
    return len(payload)


def get_catalog_rows(
    country: str,
    fulfillment: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 5000,
) -> List[Dict[str, Any]]:
    client = get_client()
    query = client.table("sku_catalog").select("*").eq("country", country.upper()).limit(limit)
    if fulfillment and fulfillment.upper() != "ALL":
        query = query.eq("fulfillment", fulfillment.upper())
    result = query.order("sku").execute()
    rows = result.data or []
    if search:
        needle = search.lower()
        rows = [
            row
            for row in rows
            if needle in (row.get("sku") or "").lower()
            or needle in (row.get("asin") or "").lower()
        ]
    return rows


def catalog_stats_from_db(country: str) -> Dict[str, Any]:
    rows = get_catalog_rows(country)
    fba = sum(1 for row in rows if row.get("fulfillment") == "FBA")
    fbm = sum(1 for row in rows if row.get("fulfillment") == "FBM")
    fbm_suffix = sum(1 for row in rows if row.get("is_fbm"))
    synced_at = None
    if rows:
        synced_at = max((row.get("synced_at") for row in rows if row.get("synced_at")), default=None)
    return {
        "total": len(rows),
        "fba": fba,
        "fbm": fbm,
        "fbm_suffix": fbm_suffix,
        "synced_at": synced_at,
        "source": "supabase",
    }


def record_sync_run(
    country: str,
    sku_count: int,
    source: str,
    created_by: Optional[str] = None,
) -> None:
    client = get_client()
    client.table("catalog_sync_runs").insert(
        {
            "country": country.upper(),
            "sku_count": sku_count,
            "source": source,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "created_by": created_by,
        }
    ).execute()


def get_sku_rule(sku: str, country: str) -> Optional[Dict[str, Any]]:
    client = get_client()
    result = (
        client.table("sku_rules")
        .select("*")
        .eq("sku", sku)
        .eq("country", country.upper())
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def list_sku_rules(country: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
    client = get_client()
    query = client.table("sku_rules").select("*").order("updated_at", desc=True).limit(limit)
    if country:
        query = query.eq("country", country.upper())
    return query.execute().data or []


def upsert_sku_rule(rule: Dict[str, Any], updated_by: Optional[str] = None) -> Dict[str, Any]:
    client = get_client()
    payload = {
        "sku": rule["sku"],
        "country": rule["country"].upper(),
        "min_price": rule.get("min_price"),
        "max_price": rule.get("max_price"),
        "fbm_discount": rule.get("fbm_discount"),
        "sync_siblings": rule.get("sync_siblings"),
        "sync_fbm": rule.get("sync_fbm"),
        "notes": rule.get("notes"),
        "updated_by": updated_by,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = client.table("sku_rules").upsert(payload, on_conflict="sku,country").execute()
    return (result.data or [payload])[0]


def delete_sku_rule(sku: str, country: str) -> None:
    client = get_client()
    client.table("sku_rules").delete().eq("sku", sku).eq("country", country.upper()).execute()


def apply_price_bounds(price: float, rule: Optional[Dict[str, Any]]) -> float:
    if not rule:
        return price
    bounded = price
    if rule.get("min_price") is not None:
        bounded = max(bounded, float(rule["min_price"]))
    if rule.get("max_price") is not None:
        bounded = min(bounded, float(rule["max_price"]))
    return round(bounded, 2)


def record_price_history(entries: List[Dict[str, Any]]) -> None:
    if not entries:
        return
    client = get_client()
    client.table("price_history").insert(entries).execute()


def list_price_history(
    country: Optional[str] = None,
    sku: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    client = get_client()
    query = client.table("price_history").select("*").order("created_at", desc=True).limit(limit)
    if country:
        query = query.eq("country", country.upper())
    if sku:
        query = query.eq("sku", sku)
    return query.execute().data or []


def get_app_settings() -> Dict[str, Any]:
    client = get_client()
    result = client.table("app_settings").select("*").eq("id", 1).limit(1).execute()
    rows = result.data or []
    if rows:
        return rows[0]
    return {
        "default_country": "DE",
        "default_region": "EU",
        "default_fbm_discount": 0.10,
        "sync_siblings": True,
        "sync_fbm": True,
    }


def update_app_settings(values: Dict[str, Any]) -> Dict[str, Any]:
    client = get_client()
    payload = {
        "default_country": values.get("default_country", "DE"),
        "default_region": values.get("default_region", "EU"),
        "default_fbm_discount": values.get("default_fbm_discount", 0.10),
        "sync_siblings": values.get("sync_siblings", True),
        "sync_fbm": values.get("sync_fbm", True),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = client.table("app_settings").update(payload).eq("id", 1).execute()
    return (result.data or [payload])[0]

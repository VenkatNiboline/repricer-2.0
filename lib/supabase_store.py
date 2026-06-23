"""Supabase persistence for catalog, rules, history, and settings."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from marketplaces import catalog_table_for_country

from env_config import load_env

ROOT = Path(__file__).parent.parent
ENV_FILE = ROOT / "ENV" / "AmazonCredentials.env"

load_env()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
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


def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
    if not is_configured():
        return None
    client = get_client()
    result = client.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    rows = result.data or []
    return rows[0] if rows else None


def upsert_catalog_rows(country: str, rows: List[Dict[str, Any]]) -> int:
    client = get_client()
    table = catalog_table_for_country(country)
    now = datetime.now(timezone.utc).isoformat()
    payload = []
    for row in rows:
        payload.append(
            {
                "sku": row["sku"],
                "asin": row.get("asin"),
                "product_name": row.get("product_name"),
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
        client.table(table).upsert(batch, on_conflict="sku").execute()
    return len(payload)


def get_catalog_rows(
    country: str,
    fulfillment: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 5000,
) -> List[Dict[str, Any]]:
    client = get_client()
    table = catalog_table_for_country(country)
    query = client.table(table).select("*").limit(limit)
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
            or needle in (row.get("product_name") or "").lower()
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


def record_price_history(entries: List[Dict[str, Any]], *, access_token: Optional[str] = None) -> None:
    _ = access_token
    if not entries:
        return
    if not is_configured():
        raise RuntimeError(
            "Cannot save price history. Set SUPABASE_SERVICE_ROLE_KEY in ENV/AmazonCredentials.env"
        )

    for entry in entries:
        if entry.get("dry_run"):
            entry["reflection_status"] = "not_applicable"
        elif not entry.get("pushed"):
            entry["reflection_status"] = "not_applicable"
        elif entry.get("verified_price") is not None:
            target = float(entry["new_price"])
            verified = float(entry["verified_price"])
            entry["reflection_status"] = "reflected" if abs(target - verified) < 0.02 else "mismatch"
            entry["reflection_checked_at"] = datetime.now(timezone.utc).isoformat()
            entry["reflection_attempts"] = 1
        else:
            entry["reflection_status"] = "pending"
            entry["reflection_attempts"] = 0

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


def list_pending_reflections(limit: int = 50) -> List[Dict[str, Any]]:
    client = get_client()
    result = (
        client.table("price_history")
        .select("*")
        .eq("reflection_status", "pending")
        .eq("pushed", True)
        .eq("dry_run", False)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def update_price_history_reflection(
    history_id: int,
    *,
    reflection_status: str,
    verified_price: Optional[float] = None,
    reflection_attempts: int,
    error: Optional[str] = None,
) -> None:
    client = get_client()
    payload: Dict[str, Any] = {
        "reflection_status": reflection_status,
        "reflection_checked_at": datetime.now(timezone.utc).isoformat(),
        "reflection_attempts": reflection_attempts,
    }
    if verified_price is not None:
        payload["verified_price"] = verified_price
    if error is not None:
        payload["error"] = error
    client.table("price_history").update(payload).eq("id", history_id).execute()


def insert_qc_run(agent_name: str) -> int:
    client = get_client()
    result = (
        client.table("qc_runs")
        .insert({"agent_name": agent_name, "status": "running"})
        .execute()
    )
    return int((result.data or [{"id": 0}])[0]["id"])


def complete_qc_run(run_id: int, *, status: str, summary: str, findings_count: int) -> None:
    client = get_client()
    client.table("qc_runs").update(
        {
            "status": status,
            "summary": summary,
            "findings_count": findings_count,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", run_id).execute()


def insert_qc_findings(findings: List[Dict[str, Any]]) -> int:
    if not findings:
        return 0
    client = get_client()
    client.table("qc_findings").insert(findings).execute()
    return len(findings)


def list_qc_findings(
    *,
    resolved: Optional[bool] = False,
    severity: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    client = get_client()
    query = client.table("qc_findings").select("*").order("created_at", desc=True).limit(limit)
    if resolved is not None:
        query = query.eq("resolved", resolved)
    if severity:
        query = query.eq("severity", severity)
    return query.execute().data or []


def resolve_qc_finding(finding_id: int) -> None:
    client = get_client()
    client.table("qc_findings").update({"resolved": True}).eq("id", finding_id).execute()


def upsert_sales_rows(rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    client = get_client()
    batch_size = 200
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("sales_daily").upsert(batch, on_conflict="ob_marketplace_id,child_asin,ob_date").execute()
    return len(rows)


def list_sales_daily(
    country: Optional[str] = None,
    sku: Optional[str] = None,
    days: int = 30,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    from price import marketplace_id_for_country

    client = get_client()
    query = client.table("sales_daily").select("*").order("ob_date", desc=True).limit(limit)
    if country:
        mp_id = marketplace_id_for_country(country.upper())
        query = query.eq("ob_marketplace_id", mp_id)
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

"""Catalog scan with Supabase persistence and local JSON fallback."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from amazon_listing import AmazonListingClient
from fulfillment_pairs import classify_fulfillment, fba_sku_for, is_fbm_sku
from price import currency_for_country, extract_current_price, marketplace_id_for_country

try:
    from supabase_store import (
        catalog_stats_from_db,
        get_catalog_rows,
        is_configured as supabase_configured,
        record_sync_run,
        upsert_catalog_rows,
    )
except ImportError:
    supabase_configured = lambda: False  # type: ignore

ROOT = Path(__file__).parent.parent
CACHE_DIR = ROOT / "data" / "cache"


def _cache_path(country: str) -> Path:
    return CACHE_DIR / f"catalog_{country.upper()}.json"


def _iter_all_listings(client: AmazonListingClient, country: str):
    page_token: Optional[str] = None
    while True:
        result = client.search_listings_items(
            countries=[country],
            included_data="summaries,attributes,offers",
            page_size=20,
            page_token=page_token,
        )
        for item in result.get("items") or []:
            yield item
        page_token = (result.get("pagination") or {}).get("nextToken")
        if not page_token:
            break


def _row_from_item(item: Dict[str, Any], country: str) -> Optional[Dict[str, Any]]:
    sku = item.get("sku") or ""
    if not sku:
        return None

    marketplace_id = marketplace_id_for_country(country)
    currency = currency_for_country(country)
    fulfillment = classify_fulfillment(sku, item, marketplace_id)
    price = extract_current_price(item, marketplace_id)
    summaries = item.get("summaries") or []
    asin = summaries[0].get("asin") if summaries else None
    product_type = summaries[0].get("productType") if summaries else None

    return {
        "sku": sku,
        "asin": asin,
        "product_type": product_type,
        "fulfillment": fulfillment,
        "price": price,
        "currency": currency,
        "fba_pair": fba_sku_for(sku) if is_fbm_sku(sku) else sku,
        "is_fbm": is_fbm_sku(sku),
    }


def load_cache(country: str) -> Optional[Dict[str, Any]]:
    path = _cache_path(country)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(country: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "country": country.upper(),
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "rows": rows,
    }
    _cache_path(country).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def get_catalog_payload(
    country: str,
    *,
    fulfillment: Optional[str] = None,
    refresh: bool = False,
) -> Dict[str, Any]:
    country = country.upper()
    if not refresh and supabase_configured():
        rows = get_catalog_rows(country, fulfillment=fulfillment)
        if rows:
            stats = catalog_stats_from_db(country)
            return {
                "country": country,
                "synced_at": stats.get("synced_at"),
                "count": len(rows),
                "rows": rows,
                "source": "supabase",
            }

    cached = load_cache(country) if not refresh else None
    if cached:
        cached["source"] = "cache"
        rows = cached.get("rows") or []
        if fulfillment and fulfillment.upper() != "ALL":
            rows = [row for row in rows if row.get("fulfillment") == fulfillment.upper()]
        cached["rows"] = rows
        cached["count"] = len(rows)
        return cached

    return {
        "country": country,
        "synced_at": None,
        "count": 0,
        "rows": [],
        "source": "empty",
    }


def scan_catalog(
    country: str,
    region: str = "EU",
    *,
    refresh: bool = False,
    max_age_seconds: int = 3600,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    country = country.upper()

    if not refresh and supabase_configured():
        rows = get_catalog_rows(country)
        if rows:
            stats = catalog_stats_from_db(country)
            return {
                "country": country,
                "synced_at": stats.get("synced_at"),
                "count": len(rows),
                "rows": rows,
                "source": "supabase",
            }

    if not refresh:
        cached = load_cache(country)
        if cached:
            synced_at = cached.get("synced_at")
            if synced_at:
                try:
                    synced_ts = datetime.fromisoformat(synced_at.replace("Z", "+00:00")).timestamp()
                    if time.time() - synced_ts < max_age_seconds:
                        cached["source"] = "cache"
                        return cached
                except ValueError:
                    pass

    client = AmazonListingClient(region=region)
    rows: List[Dict[str, Any]] = []
    for item in _iter_all_listings(client, country):
        row = _row_from_item(item, country)
        if row:
            rows.append(row)

    rows.sort(key=lambda row: row["sku"])
    payload = save_cache(country, rows)
    payload["source"] = "live"

    if supabase_configured():
        upsert_catalog_rows(country, rows)
        record_sync_run(country, len(rows), "live", created_by=created_by)
        payload["source"] = "supabase"

    return payload


def catalog_stats(payload: Dict[str, Any]) -> Dict[str, Any]:
    rows = payload.get("rows") or []
    fba = sum(1 for row in rows if row.get("fulfillment") == "FBA")
    fbm = sum(1 for row in rows if row.get("fulfillment") == "FBM")
    fbm_suffix = sum(1 for row in rows if row.get("is_fbm"))
    return {
        "total": len(rows),
        "fba": fba,
        "fbm": fbm,
        "fbm_suffix": fbm_suffix,
        "synced_at": payload.get("synced_at"),
        "source": payload.get("source", "unknown"),
    }

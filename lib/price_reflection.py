"""Poll Amazon until listing price reflects a target price change."""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from amazon_listing import AmazonListingClient
from price import extract_current_price, marketplace_id_for_country, prices_match
from supabase_store import (
    is_configured,
    list_pending_reflections,
    update_price_history_reflection,
)

MAX_ATTEMPTS = 30
PENDING_MAX_AGE_MINUTES = 30


def verify_history_row(row: Dict[str, Any], region: str = "EU") -> Dict[str, Any]:
    """Check one price_history row against live Amazon listing."""
    history_id = int(row["id"])
    sku = row["sku"]
    country = row["country"]
    target = float(row["new_price"])
    attempts = int(row.get("reflection_attempts") or 0) + 1
    marketplace_id = marketplace_id_for_country(country)

    try:
        client = AmazonListingClient(region=region)
        listing = client.get_listing(sku, countries=[country])
        verified = extract_current_price(listing, marketplace_id)
    except Exception as exc:
        status = "timeout" if attempts >= MAX_ATTEMPTS else "pending"
        update_price_history_reflection(
            history_id,
            reflection_status=status,
            reflection_attempts=attempts,
            error=str(exc),
        )
        return {"id": history_id, "reflection_status": status, "error": str(exc)}

    if verified is not None and prices_match(verified, target):
        update_price_history_reflection(
            history_id,
            reflection_status="reflected",
            verified_price=verified,
            reflection_attempts=attempts,
        )
        return {"id": history_id, "reflection_status": "reflected", "verified_price": verified}

    created = row.get("created_at")
    stale = False
    if created:
        try:
            created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            age_min = (datetime.now(timezone.utc) - created_dt).total_seconds() / 60
            stale = age_min > PENDING_MAX_AGE_MINUTES
        except Exception:
            stale = attempts >= MAX_ATTEMPTS

    if stale or attempts >= MAX_ATTEMPTS:
        status = "timeout" if verified is None else "mismatch"
        update_price_history_reflection(
            history_id,
            reflection_status=status,
            verified_price=verified,
            reflection_attempts=attempts,
            error=f"expected {target:.2f}, got {verified}",
        )
        return {
            "id": history_id,
            "reflection_status": status,
            "verified_price": verified,
        }

    update_price_history_reflection(
        history_id,
        reflection_status="pending",
        verified_price=verified,
        reflection_attempts=attempts,
    )
    return {"id": history_id, "reflection_status": "pending", "verified_price": verified}


def verify_pending_reflections(region: str = "EU", limit: int = 50) -> List[Dict[str, Any]]:
    if not is_configured():
        return []
    rows = list_pending_reflections(limit=limit)
    return [verify_history_row(row, region=region) for row in rows]

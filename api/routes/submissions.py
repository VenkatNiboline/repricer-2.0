"""Look up Amazon listing state for a price submission."""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from amazon_listing import AmazonListingClient, MARKETPLACE_IDS
from api.auth import get_access_token, optional_user_id
from api.errors import raise_http_error
from price import currency_for_country, extract_current_price, marketplace_id_for_country
from supabase_store import get_price_history_by_submission_id, is_readable

router = APIRouter()


class SubmissionLookupResponse(BaseModel):
    submission_id: str
    sku: str
    country: str
    currency: str
    history: Optional[Dict[str, Any]] = None
    current_price: Optional[float] = None
    listing: Dict[str, Any]
    note: str


@router.get("/submissions/lookup", response_model=SubmissionLookupResponse)
def lookup_submission(
    submission_id: str = Query(..., min_length=3),
    country: Optional[str] = Query(None),
    sku: Optional[str] = Query(None),
    region: str = Query("EU"),
    user_id: Optional[str] = Depends(optional_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    _ = user_id
    submission_id = submission_id.strip()
    history = None

    if is_readable():
        try:
            history = get_price_history_by_submission_id(submission_id, access_token=access_token)
        except RuntimeError:
            history = None

    resolved_sku = (sku or (history or {}).get("sku") or "").strip()
    resolved_country = (country or (history or {}).get("country") or "DE").upper()

    if not resolved_sku:
        raise HTTPException(
            400,
            "SKU not found for this submission ID. Enter the SKU manually or pick a row from History.",
        )
    if resolved_country not in MARKETPLACE_IDS:
        raise HTTPException(400, f"Unknown country: {resolved_country}")

    marketplace_id = marketplace_id_for_country(resolved_country)
    currency = currency_for_country(resolved_country)

    try:
        client = AmazonListingClient(region=region)
        listing = client.get_listing(
            resolved_sku,
            countries=[resolved_country],
            included_data="summaries,attributes,offers,issues",
        )
    except Exception as exc:
        raise_http_error(exc, status_code=502, client_message="Could not fetch listing from Amazon")

    current_price = extract_current_price(listing, marketplace_id)
    note = (
        "Amazon has no API to query by submissionId directly. "
        "This response is the live Listings Items JSON for the SKU linked to this submission in your history."
    )

    return SubmissionLookupResponse(
        submission_id=submission_id,
        sku=resolved_sku,
        country=resolved_country,
        currency=currency,
        history=history,
        current_price=current_price,
        listing=listing,
        note=note,
    )

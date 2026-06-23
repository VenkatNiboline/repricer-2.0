"""Price update endpoints."""

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from amazon_listing import AmazonListingClient, MARKETPLACE_IDS
from api.auth import get_current_user_id
from fulfillment_pairs import (
    DEFAULT_FBM_DISCOUNT,
    PlannedUpdate,
    append_fbm_updates,
    normalize_fba_anchor,
)
from price import (
    build_price_patch,
    currency_for_country,
    extract_current_price,
    get_product_type,
    marketplace_id_for_country,
    prices_match,
)
from supabase_store import (
    apply_price_bounds,
    get_sku_rule,
    is_configured as supabase_configured,
    record_price_history,
)
from variations import compute_linked_prices, fetch_variation_family

router = APIRouter()


class PriceUpdateRequest(BaseModel):
    sku: str
    price: float = Field(..., gt=0)
    country: str = "DE"
    region: str = "EU"
    dry_run: bool = True
    verify: bool = True
    sync_siblings: bool = True
    sync_fbm: bool = True
    double_only: bool = False
    fbm_discount: float = Field(DEFAULT_FBM_DISCOUNT, ge=0, lt=1)
    exclude_skus: list[str] = []


class UpdateResultOut(BaseModel):
    sku: str
    current_price: Optional[float]
    target_price: float
    validation_ok: bool
    pushed: bool
    submission_id: Optional[str] = None
    status: Optional[str] = None
    verified_price: Optional[float] = None
    error: Optional[str] = None
    link_kind: str = "primary"


class PriceUpdateResponse(BaseModel):
    country: str
    currency: str
    parent_sku: Optional[str]
    results: list[UpdateResultOut]
    history_saved: bool = True
    history_error: Optional[str] = None


def _validate_patch(client, sku, country, patches, product_type):
    result = client.patch_listing(
        sku=sku,
        patches=patches,
        product_type=product_type,
        countries=[country],
        mode="VALIDATION_PREVIEW",
    )
    if result.get("status") != "VALID":
        raise RuntimeError(str(result.get("issues", [])))


def _update_one(client, sku, target_price, country, marketplace_id, currency, dry_run, verify):
    listing = client.get_listing(sku, countries=[country])
    product_type = get_product_type(listing)
    if not product_type:
        return UpdateResultOut(
            sku=sku,
            current_price=None,
            target_price=target_price,
            validation_ok=False,
            pushed=False,
            error="could not determine productType",
        )

    current_price = extract_current_price(listing, marketplace_id)
    patches = build_price_patch(target_price, marketplace_id, currency)

    try:
        _validate_patch(client, sku, country, patches, product_type)
    except Exception as exc:
        return UpdateResultOut(
            sku=sku,
            current_price=current_price,
            target_price=target_price,
            validation_ok=False,
            pushed=False,
            error=str(exc),
        )

    if dry_run:
        return UpdateResultOut(
            sku=sku,
            current_price=current_price,
            target_price=target_price,
            validation_ok=True,
            pushed=False,
            status="DRY_RUN",
        )

    try:
        result = client.patch_listing(
            sku=sku,
            patches=patches,
            product_type=product_type,
            countries=[country],
            mode=None,
        )
    except Exception as exc:
        return UpdateResultOut(
            sku=sku,
            current_price=current_price,
            target_price=target_price,
            validation_ok=True,
            pushed=False,
            error=str(exc),
        )

    verified_price = None
    error = None
    if verify:
        listing = client.get_listing(sku, countries=[country])
        verified_price = extract_current_price(listing, marketplace_id)
        if not prices_match(verified_price, target_price):
            error = f"expected {target_price:.2f}, got {verified_price}"

    return UpdateResultOut(
        sku=sku,
        current_price=current_price,
        target_price=target_price,
        validation_ok=True,
        pushed=True,
        submission_id=result.get("submissionId"),
        status=result.get("status"),
        verified_price=verified_price,
        error=error,
    )


def _bounded_price(sku: str, country: str, price: float) -> float:
    if not supabase_configured():
        return price
    rule = get_sku_rule(sku, country)
    return apply_price_bounds(price, rule)


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip() or None


@router.post("/repricer/update", response_model=PriceUpdateResponse)
def update_price(
    body: PriceUpdateRequest,
    user_id: Optional[str] = Depends(get_current_user_id),
    authorization: Optional[str] = Header(default=None),
):
    country = body.country.upper()
    if country not in MARKETPLACE_IDS:
        raise HTTPException(400, f"Unknown country: {country}")

    currency = currency_for_country(country)
    marketplace_id = marketplace_id_for_country(country)

    try:
        client = AmazonListingClient(region=body.region)
        fba_sku, fba_price = normalize_fba_anchor(body.sku, body.price, body.fbm_discount)
        fba_price = _bounded_price(fba_sku, country, fba_price)

        primary_rule = get_sku_rule(fba_sku, country) if supabase_configured() else None
        sync_siblings = body.sync_siblings
        sync_fbm = body.sync_fbm
        fbm_discount = body.fbm_discount
        if primary_rule:
            if primary_rule.get("sync_siblings") is not None:
                sync_siblings = bool(primary_rule["sync_siblings"])
            if primary_rule.get("sync_fbm") is not None:
                sync_fbm = bool(primary_rule["sync_fbm"])
            if primary_rule.get("fbm_discount") is not None:
                fbm_discount = float(primary_rule["fbm_discount"])

        parent_sku, members = fetch_variation_family(client, fba_sku, country)

        plan: list[PlannedUpdate] = [
            PlannedUpdate(sku=fba_sku, target_price=fba_price, link_kind="primary")
        ]
        if sync_siblings:
            for update in compute_linked_prices(
                fba_sku,
                fba_price,
                members,
                double_only=body.double_only,
                exclude_skus=body.exclude_skus,
            ):
                plan.append(
                    PlannedUpdate(
                        sku=update.sku,
                        target_price=_bounded_price(update.sku, country, update.target_price),
                        linked=True,
                        multiplier=update.multiplier,
                        link_kind="variation",
                    )
                )
        if sync_fbm:
            plan = append_fbm_updates(client, plan, country, fbm_discount)
            for planned in plan:
                if planned.link_kind == "fbm":
                    planned.target_price = _bounded_price(planned.sku, country, planned.target_price)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

    results: list[UpdateResultOut] = []
    history_entries = []
    for planned in plan:
        result = _update_one(
            client,
            planned.sku,
            planned.target_price,
            country,
            marketplace_id,
            currency,
            body.dry_run,
            body.verify,
        )
        result.link_kind = planned.link_kind
        results.append(result)
        history_entries.append(
            {
                "sku": result.sku,
                "country": country,
                "old_price": result.current_price,
                "new_price": result.target_price,
                "currency": currency,
                "link_kind": result.link_kind,
                "parent_sku": parent_sku,
                "dry_run": body.dry_run,
                "validation_ok": result.validation_ok,
                "pushed": result.pushed,
                "submission_id": result.submission_id,
                "verified_price": result.verified_price,
                "error": result.error,
                "created_by": user_id,
            }
        )

    history_saved = True
    history_error = None
    try:
        record_price_history(history_entries)
    except Exception as exc:
        history_saved = False
        history_error = str(exc)

    if history_saved and not body.dry_run:
        try:
            from qc.runner import run_after_repricing

            run_after_repricing()
        except Exception:
            pass

    return PriceUpdateResponse(
        country=country,
        currency=currency,
        parent_sku=parent_sku,
        results=results,
        history_saved=history_saved,
        history_error=history_error,
    )

"""SKU discovery endpoints."""

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from amazon_listing import AmazonListingClient, MARKETPLACE_IDS
from fulfillment_pairs import (
    DEFAULT_FBM_DISCOUNT,
    classify_fulfillment,
    fba_sku_for,
    fbm_counterpart_exists,
    fbm_price_from_fba,
    is_fbm_sku,
)
from price import currency_for_country, extract_current_price, marketplace_id_for_country
from catalog import catalog_stats, get_catalog_payload, scan_catalog
from api.auth import get_access_token, require_user_id
from api.errors import raise_http_error
from env_config import AMAZON_DISABLED_MESSAGE, AmazonApiDisabledError, amazon_api_enabled
from supabase_store import get_catalog_row, is_readable

from variations import compute_linked_prices, fetch_variation_family

router = APIRouter()


class MarketplaceInfo(BaseModel):
    code: str
    currency: str


class SkuSummary(BaseModel):
    sku: str
    fulfillment: str
    price: Optional[float]
    currency: str
    fba_pair: Optional[str] = None
    fbm_pair: Optional[str] = None
    parent_sku: Optional[str] = None


class VariationMemberOut(BaseModel):
    sku: str
    units: float
    current_price: Optional[float]
    size_label: str
    is_source: bool = False


class LinkedPriceOut(BaseModel):
    sku: str
    units: float
    current_price: Optional[float]
    target_price: float
    multiplier: float
    link_kind: str


class VariationPreview(BaseModel):
    sku: str
    country: str
    currency: str
    parent_sku: Optional[str]
    fbm_pair: Optional[str]
    members: list[VariationMemberOut]
    linked_updates: list[LinkedPriceOut]
    fbm_target_price: Optional[float]


@router.get("/marketplaces", response_model=list[MarketplaceInfo])
def list_marketplaces():
    return [
        MarketplaceInfo(code=code, currency=currency_for_country(code))
        for code in sorted(MARKETPLACE_IDS)
    ]


@router.get("/skus/{sku}", response_model=SkuSummary)
def get_sku(
    sku: str,
    country: str = Query("DE"),
    region: str = Query("EU"),
    live: bool = Query(True, description="Read live price from Amazon (recommended)"),
    user_id: str = Depends(require_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    _ = user_id
    country = country.upper()
    if country not in MARKETPLACE_IDS:
        raise HTTPException(400, f"Unknown country: {country}")

    currency = currency_for_country(country)
    marketplace_id = marketplace_id_for_country(country)

    if live:
        try:
            client = AmazonListingClient(region=region)
            listing = client.get_listing(sku, countries=[country])
            fulfillment = classify_fulfillment(sku, listing, marketplace_id)
            price = extract_current_price(listing, marketplace_id)
            fbm_pair = fbm_counterpart_exists(
                client, fba_sku_for(sku) if is_fbm_sku(sku) else sku, country
            )
            parent_sku = None
            try:
                parent_sku, _ = fetch_variation_family(client, sku, country)
            except Exception:
                pass
            return SkuSummary(
                sku=sku,
                fulfillment=fulfillment,
                price=price,
                currency=currency,
                fba_pair=fba_sku_for(sku) if is_fbm_sku(sku) else sku,
                fbm_pair=fbm_pair,
                parent_sku=parent_sku,
            )
        except AmazonApiDisabledError:
            pass
        except Exception:
            pass

    if is_readable():
        try:
            row = get_catalog_row(country, sku, access_token=access_token)
            if row:
                catalog_price = row.get("price")
                return SkuSummary(
                    sku=row["sku"],
                    fulfillment=row.get("fulfillment", "UNKNOWN"),
                    price=float(catalog_price) if catalog_price is not None else None,
                    currency=row.get("currency") or currency,
                    fba_pair=row.get("fba_pair") or row["sku"],
                    fbm_pair=None,
                    parent_sku=row.get("parent_sku"),
                )
        except RuntimeError:
            pass

    if not amazon_api_enabled():
        raise HTTPException(503, AMAZON_DISABLED_MESSAGE)

    try:
        client = AmazonListingClient(region=region)
        listing = client.get_listing(sku, countries=[country])
        parent_sku, members = fetch_variation_family(client, sku, country)
    except Exception as exc:
        raise_http_error(exc, status_code=404, client_message="SKU not found")

    fulfillment = classify_fulfillment(sku, listing, marketplace_id)
    price = extract_current_price(listing, marketplace_id)

    fba_pair = fba_sku_for(sku) if is_fbm_sku(sku) else sku
    fbm_pair = fbm_counterpart_exists(client, fba_sku_for(sku) if is_fbm_sku(sku) else sku, country)

    return SkuSummary(
        sku=sku,
        fulfillment=fulfillment,
        price=price,
        currency=currency,
        fba_pair=fba_sku_for(sku) if is_fbm_sku(sku) else sku,
        fbm_pair=fbm_pair,
        parent_sku=parent_sku,
    )


@router.get("/skus/{sku}/preview", response_model=VariationPreview)
def preview_price_update(
    sku: str,
    price: float = Query(..., gt=0),
    country: str = Query("DE"),
    region: str = Query("EU"),
    double_only: bool = Query(False),
    sync_siblings: bool = Query(True),
    sync_fbm: bool = Query(True),
    fbm_discount: float = Query(DEFAULT_FBM_DISCOUNT, ge=0, lt=1),
    user_id: str = Depends(require_user_id),
):
    _ = user_id
    country = country.upper()
    if country not in MARKETPLACE_IDS:
        raise HTTPException(400, f"Unknown country: {country}")

    try:
        client = AmazonListingClient(region=region)
        parent_sku, members = fetch_variation_family(client, sku, country)
        fbm_pair = fbm_counterpart_exists(client, sku, country) if not is_fbm_sku(sku) else None
    except Exception as exc:
        raise_http_error(exc, status_code=404, client_message="SKU not found")

    currency = currency_for_country(country)
    linked = []
    if sync_siblings:
        for update in compute_linked_prices(sku, price, members, double_only=double_only):
            linked.append(
                LinkedPriceOut(
                    sku=update.sku,
                    units=update.units,
                    current_price=update.current_price,
                    target_price=update.target_price,
                    multiplier=update.multiplier,
                    link_kind="variation",
                )
            )

    if sync_fbm and fbm_pair:
        linked.append(
            LinkedPriceOut(
                sku=fbm_pair,
                units=0,
                current_price=None,
                target_price=fbm_price_from_fba(price, fbm_discount),
                multiplier=1 - fbm_discount,
                link_kind="fbm",
            )
        )

    return VariationPreview(
        sku=sku,
        country=country,
        currency=currency,
        parent_sku=parent_sku,
        fbm_pair=fbm_pair,
        members=[
            VariationMemberOut(
                sku=m.sku,
                units=m.units,
                current_price=m.current_price,
                size_label=m.size_label,
                is_source=m.sku == sku,
            )
            for m in members
        ],
        linked_updates=linked,
        fbm_target_price=fbm_price_from_fba(price, fbm_discount) if fbm_pair and sync_fbm else None,
    )


class FbmSkuRow(BaseModel):
    sku: str
    fba_pair: str
    price: Optional[float]
    currency: str
    detected_by: str


class CatalogRow(BaseModel):
    sku: str
    asin: Optional[str] = None
    product_name: Optional[str] = None
    product_type: Optional[str] = None
    fulfillment: str
    price: Optional[float]
    currency: str
    fba_pair: str = ""
    is_fbm: bool = False


def _as_catalog_row(row: dict) -> CatalogRow:
    return CatalogRow(
        **{
            **row,
            "fba_pair": row.get("fba_pair") or row.get("sku") or "",
            "is_fbm": bool(row.get("is_fbm")),
        }
    )


class CatalogStats(BaseModel):
    total: int
    fba: int
    fbm: int
    fbm_suffix: int
    synced_at: Optional[str]
    source: str


class CatalogResponse(BaseModel):
    country: str
    synced_at: Optional[str]
    source: str
    count: int
    stats: CatalogStats
    rows: list[CatalogRow]


@router.get("/catalog/stats", response_model=CatalogStats)
def get_catalog_stats(
    country: str = Query("DE"),
    region: str = Query("EU"),
    refresh: bool = Query(False),
    user_id: str = Depends(require_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    _ = user_id
    country = country.upper()
    if country not in MARKETPLACE_IDS:
        raise HTTPException(400, f"Unknown country: {country}")
    payload = (
        get_catalog_payload(country, refresh=False, access_token=access_token)
        if not refresh
        else scan_catalog(country, region, refresh=True, access_token=access_token)
    )
    return CatalogStats(**catalog_stats(payload))


@router.post("/catalog/sync", response_model=CatalogResponse)
def sync_catalog_endpoint(
    country: str = Query("DE"),
    region: str = Query("EU"),
    user_id: str = Depends(require_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    country = country.upper()
    if country not in MARKETPLACE_IDS:
        raise HTTPException(400, f"Unknown country: {country}")
    try:
        payload = scan_catalog(
            country, region, refresh=True, created_by=user_id, access_token=access_token
        )
    except AmazonApiDisabledError as exc:
        raise HTTPException(503, str(exc)) from exc
    rows = payload.get("rows") or []
    stats = catalog_stats(payload)
    return CatalogResponse(
        country=country,
        synced_at=payload.get("synced_at"),
        source=payload.get("source", "unknown"),
        count=len(rows),
        stats=CatalogStats(**stats),
        rows=[_as_catalog_row(row) for row in rows],
    )


@router.get("/catalog", response_model=CatalogResponse)
def get_catalog(
    country: str = Query("DE"),
    region: str = Query("EU"),
    refresh: bool = Query(False),
    fulfillment: Optional[str] = Query(None, description="Filter: FBA, FBM, or ALL"),
    user_id: str = Depends(require_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    country = country.upper()
    if country not in MARKETPLACE_IDS:
        raise HTTPException(400, f"Unknown country: {country}")

    if refresh:
        payload = scan_catalog(
            country, region, refresh=True, created_by=user_id, access_token=access_token
        )
    else:
        payload = get_catalog_payload(
            country, fulfillment=fulfillment, refresh=False, access_token=access_token
        )

    rows = payload.get("rows") or []
    if fulfillment and fulfillment.upper() != "ALL":
        rows = [row for row in rows if row.get("fulfillment") == fulfillment.upper()]

    stats = catalog_stats({**payload, "rows": rows})
    return CatalogResponse(
        country=country,
        synced_at=payload.get("synced_at"),
        source=payload.get("source", "unknown"),
        count=len(rows),
        stats=CatalogStats(**stats),
        rows=[_as_catalog_row(row) for row in rows],
    )


@router.get("/fbm-skus", response_model=list[FbmSkuRow])
def list_fbm_skus(
    country: str = Query("DE"),
    region: str = Query("EU"),
    suffix_only: bool = Query(True),
    refresh: bool = Query(False),
    user_id: str = Depends(require_user_id),
    access_token: Optional[str] = Depends(get_access_token),
):
    _ = user_id
    country = country.upper()
    if country not in MARKETPLACE_IDS:
        raise HTTPException(400, f"Unknown country: {country}")

    payload = scan_catalog(country, region, refresh=refresh, access_token=access_token)
    rows: list[FbmSkuRow] = []
    for row in payload.get("rows") or []:
        if row.get("fulfillment") != "FBM":
            continue
        if suffix_only and not row.get("is_fbm"):
            continue
        rows.append(
            FbmSkuRow(
                sku=row["sku"],
                fba_pair=row.get("fba_pair") or "",
                price=row.get("price"),
                currency=row.get("currency") or currency_for_country(country),
                detected_by="suffix" if row.get("is_fbm") else "fulfillment_channel",
            )
        )
    return rows

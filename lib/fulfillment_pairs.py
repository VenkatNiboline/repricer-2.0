"""FBA/FBM SKU pairing and linked pricing."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from amazon_listing import AmazonListingClient

FBM_SUFFIX = "FBM"
FBA_CHANNELS = {"AMAZON_EU", "AMAZON_NA", "AMAZON_JP", "AMAZON_IN", "AMAZON_CN"}
DEFAULT_FBM_DISCOUNT = 0.10


@dataclass
class PlannedUpdate:
    sku: str
    target_price: float
    linked: bool = False
    multiplier: Optional[float] = None
    link_kind: str = "primary"  # primary | variation | fbm


def is_fbm_sku(sku: str) -> bool:
    return sku.upper().endswith(FBM_SUFFIX)


def fulfillment_channels(listing: Dict[str, Any], marketplace_id: Optional[str] = None) -> List[str]:
    attrs = listing.get("attributes") or {}
    entries = attrs.get("fulfillment_availability") or []
    codes: List[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if marketplace_id and entry.get("marketplace_id") not in (None, marketplace_id):
            continue
        code = entry.get("fulfillment_channel_code")
        if code:
            codes.append(code)
    return codes


def is_fbm_listing(listing: Dict[str, Any], marketplace_id: Optional[str] = None) -> bool:
    codes = fulfillment_channels(listing, marketplace_id)
    if not codes:
        return False
    if any(code in FBA_CHANNELS or (code and code.startswith("AMAZON")) for code in codes):
        return False
    return "DEFAULT" in codes


def classify_fulfillment(sku: str, listing: Dict[str, Any], marketplace_id: Optional[str] = None) -> str:
    if is_fbm_sku(sku):
        return "FBM"
    codes = fulfillment_channels(listing, marketplace_id)
    if any(code in FBA_CHANNELS or (code and code.startswith("AMAZON")) for code in codes):
        return "FBA"
    if "DEFAULT" in codes:
        return "FBM"
    return "UNKNOWN"


def fbm_sku_for(fba_sku: str) -> str:
    if is_fbm_sku(fba_sku):
        return fba_sku
    return fba_sku + FBM_SUFFIX


def fba_sku_for(sku: str) -> str:
    if is_fbm_sku(sku):
        return sku[: -len(FBM_SUFFIX)]
    return sku


def fbm_price_from_fba(fba_price: float, discount: float = DEFAULT_FBM_DISCOUNT) -> float:
    if discount < 0 or discount >= 1:
        raise ValueError("FBM discount must be between 0 and 1 (exclusive).")
    return round(fba_price * (1 - discount), 2)


def fba_price_from_fbm(fbm_price: float, discount: float = DEFAULT_FBM_DISCOUNT) -> float:
    if discount < 0 or discount >= 1:
        raise ValueError("FBM discount must be between 0 and 1 (exclusive).")
    return round(fbm_price / (1 - discount), 2)


def normalize_fba_anchor(sku: str, price: float, discount: float = DEFAULT_FBM_DISCOUNT) -> Tuple[str, float]:
    """Return the FBA SKU and FBA target price for repricing."""
    if is_fbm_sku(sku):
        return fba_sku_for(sku), fba_price_from_fbm(price, discount)
    return sku, price


def fbm_counterpart_exists(
    client: AmazonListingClient,
    fba_sku: str,
    country: str,
) -> Optional[str]:
    if is_fbm_sku(fba_sku):
        return None

    fbm_sku = fbm_sku_for(fba_sku)
    try:
        client.get_listing(fbm_sku, countries=[country])
        return fbm_sku
    except Exception:
        return None


def append_fbm_updates(
    client: AmazonListingClient,
    plan: List[PlannedUpdate],
    country: str,
    discount: float = DEFAULT_FBM_DISCOUNT,
) -> List[PlannedUpdate]:
    """Add FBM SKU updates at a discount below each FBA SKU in the plan."""
    existing = {update.sku for update in plan}
    fbm_updates: List[PlannedUpdate] = []

    for update in plan:
        if is_fbm_sku(update.sku):
            continue

        fbm_sku = fbm_counterpart_exists(client, update.sku, country)
        if not fbm_sku or fbm_sku in existing:
            continue

        fbm_updates.append(
            PlannedUpdate(
                sku=fbm_sku,
                target_price=fbm_price_from_fba(update.target_price, discount),
                linked=True,
                multiplier=1 - discount,
                link_kind="fbm",
            )
        )
        existing.add(fbm_sku)

    return plan + fbm_updates

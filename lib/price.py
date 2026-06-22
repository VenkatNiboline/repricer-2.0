"""Price extraction and patch helpers for Listings Items API."""

from typing import Any, Dict, List, Optional

from amazon_listing import MARKETPLACE_IDS

COUNTRY_CURRENCIES = {
    "DE": "EUR",
    "FR": "EUR",
    "ES": "EUR",
    "IT": "EUR",
    "NL": "EUR",
    "BE": "EUR",
    "IE": "EUR",
    "UK": "GBP",
    "PL": "PLN",
    "SE": "SEK",
    "US": "USD",
    "CA": "CAD",
    "MX": "MXN",
    "JP": "JPY",
    "AU": "AUD",
}


def currency_for_country(country: str) -> str:
    return COUNTRY_CURRENCIES.get(country.upper(), "EUR")


def marketplace_id_for_country(country: str) -> str:
    code = country.upper()
    if code not in MARKETPLACE_IDS:
        raise ValueError(f"Unknown country code: {country}")
    return MARKETPLACE_IDS[code]


def get_product_type(listing: Dict[str, Any]) -> str:
    summaries = listing.get("summaries") or []
    if not summaries:
        return ""
    return summaries[0].get("productType") or ""


def _price_from_purchasable_offer(
    offers: List[Dict[str, Any]], marketplace_id: str
) -> Optional[float]:
    for offer in offers:
        if offer.get("marketplace_id") != marketplace_id:
            continue
        our_prices = offer.get("our_price") or []
        for our_price in our_prices:
            for schedule in our_price.get("schedule") or []:
                value = schedule.get("value_with_tax")
                if value is not None:
                    return float(value)
    return None


def _price_from_offers_section(
    offers: List[Dict[str, Any]], marketplace_id: str
) -> Optional[float]:
    for offer in offers:
        if offer.get("marketplaceId") != marketplace_id:
            continue
        price = offer.get("price") or {}
        amount = price.get("amount")
        if amount is not None:
            return float(amount)
    return None


def extract_current_price(listing: Dict[str, Any], marketplace_id: str) -> Optional[float]:
    attrs = listing.get("attributes") or {}
    purchasable = attrs.get("purchasable_offer") or []
    price = _price_from_purchasable_offer(purchasable, marketplace_id)
    if price is not None:
        return price

    offers = listing.get("offers") or []
    return _price_from_offers_section(offers, marketplace_id)


def build_price_patch(price: float, marketplace_id: str, currency: str) -> List[Dict[str, Any]]:
    return [
        {
            "op": "replace",
            "path": "/attributes/purchasable_offer",
            "value": [
                {
                    "currency": currency,
                    "audience": "ALL",
                    "our_price": [{"schedule": [{"value_with_tax": price}]}],
                    "marketplace_id": marketplace_id,
                }
            ],
        }
    ]


def prices_match(actual: Optional[float], target: float, tolerance: float = 0.01) -> bool:
    if actual is None:
        return False
    return abs(actual - target) <= tolerance

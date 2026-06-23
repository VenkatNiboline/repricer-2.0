"""EU marketplace definitions shared by catalog sync and API."""

from typing import Dict, List, TypedDict

from amazon_listing import MARKETPLACE_IDS


class Marketplace(TypedDict):
    code: str
    label: str
    currency: str
    region: str


EU_MARKETPLACES: List[Marketplace] = [
    {"code": "DE", "label": "Germany", "currency": "EUR", "region": "EU"},
    {"code": "FR", "label": "France", "currency": "EUR", "region": "EU"},
    {"code": "IT", "label": "Italy", "currency": "EUR", "region": "EU"},
    {"code": "ES", "label": "Spain", "currency": "EUR", "region": "EU"},
    {"code": "NL", "label": "Netherlands", "currency": "EUR", "region": "EU"},
    {"code": "BE", "label": "Belgium", "currency": "EUR", "region": "EU"},
    {"code": "PL", "label": "Poland", "currency": "PLN", "region": "EU"},
    {"code": "SE", "label": "Sweden", "currency": "SEK", "region": "EU"},
    {"code": "UK", "label": "United Kingdom", "currency": "GBP", "region": "EU"},
]

MARKETPLACE_BY_CODE: Dict[str, Marketplace] = {m["code"]: m for m in EU_MARKETPLACES}


def is_supported_marketplace(country: str) -> bool:
    return country.upper() in MARKETPLACE_BY_CODE


def catalog_table_for_country(country: str) -> str:
    code = country.upper()
    if code not in MARKETPLACE_BY_CODE:
        raise ValueError(f"Unsupported marketplace: {country}")
    return f"sku_catalog_{code.lower()}"


def marketplace_id_for_country(country: str) -> str:
    code = country.upper()
    if code not in MARKETPLACE_IDS:
        raise ValueError(f"Unsupported marketplace: {country}")
    return MARKETPLACE_IDS[code]


def country_for_marketplace_id(marketplace_id: str) -> str | None:
    for code, mp_id in MARKETPLACE_IDS.items():
        if mp_id == marketplace_id:
            return code
    return None

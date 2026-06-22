"""Detect variation families and compute proportional linked prices."""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from amazon_listing import AmazonListingClient
from price import extract_current_price, marketplace_id_for_country

SIZE_UNIT_PATTERN = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*[x×]", re.IGNORECASE)
STUECK_COUNT_PATTERN = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*Stück", re.IGNORECASE)
VOLUME_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*ml", re.IGNORECASE)


@dataclass
class VariationMember:
    sku: str
    units: float
    current_price: Optional[float]
    size_label: str
    product_type: str


@dataclass
class LinkedPriceUpdate:
    sku: str
    units: float
    current_price: Optional[float]
    target_price: float
    multiplier: float


def _attribute_entries(attrs: Dict[str, Any], name: str, marketplace_id: str) -> List[Dict[str, Any]]:
    entries = attrs.get(name) or []
    scoped = [entry for entry in entries if entry.get("marketplace_id") in (None, marketplace_id)]
    return scoped or entries


def _parse_size_declared_units(size_label: str) -> Optional[float]:
    if not size_label:
        return None

    match = SIZE_UNIT_PATTERN.match(size_label)
    if match:
        return float(match.group(1).replace(",", "."))

    match = STUECK_COUNT_PATTERN.match(size_label)
    if match:
        return float(match.group(1).replace(",", "."))

    return None


def extract_volume_ml(size_label: str) -> Optional[float]:
    match = VOLUME_PATTERN.search(size_label or "")
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def is_consistent_pack_member(member: VariationMember) -> bool:
    declared_units = _parse_size_declared_units(member.size_label)
    if declared_units is None:
        return True
    return abs(declared_units - member.units) < 0.01


def same_product_line(source: VariationMember, target: VariationMember) -> bool:
    if not is_consistent_pack_member(source) or not is_consistent_pack_member(target):
        return False

    source_volume = extract_volume_ml(source.size_label)
    target_volume = extract_volume_ml(target.size_label)

    if source_volume is not None and target_volume is not None:
        return abs(source_volume - target_volume) < 0.01

    if source_volume is not None or target_volume is not None:
        return False

    return True


def extract_unit_count(listing: Dict[str, Any], marketplace_id: str) -> Optional[float]:
    attrs = listing.get("attributes") or {}

    for key in ("number_of_items", "unit_count"):
        for entry in _attribute_entries(attrs, key, marketplace_id):
            value = entry.get("value")
            if value is not None:
                count = float(value)
                if count > 0:
                    return count

    for entry in _attribute_entries(attrs, "size", marketplace_id):
        size_value = entry.get("value") or ""
        declared = _parse_size_declared_units(size_value)
        if declared is not None:
            return declared

    return None


def extract_parent_sku(listing: Dict[str, Any], marketplace_id: str) -> Optional[str]:
    attrs = listing.get("attributes") or {}
    for entry in _attribute_entries(attrs, "child_parent_sku_relationship", marketplace_id):
        parent_sku = entry.get("parent_sku")
        if parent_sku:
            return parent_sku
    return None


def extract_size_label(listing: Dict[str, Any], marketplace_id: str) -> str:
    attrs = listing.get("attributes") or {}
    for entry in _attribute_entries(attrs, "size", marketplace_id):
        value = entry.get("value")
        if value:
            return str(value)
    return ""


def _member_from_item(item: Dict[str, Any], marketplace_id: str) -> Optional[VariationMember]:
    sku = item.get("sku")
    if not sku:
        return None

    units = extract_unit_count(item, marketplace_id)
    if units is None:
        return None

    summaries = item.get("summaries") or []
    product_type = summaries[0].get("productType", "") if summaries else ""

    return VariationMember(
        sku=sku,
        units=units,
        current_price=extract_current_price(item, marketplace_id),
        size_label=extract_size_label(item, marketplace_id),
        product_type=product_type,
    )


def fetch_variation_family(
    client: AmazonListingClient,
    sku: str,
    country: str,
) -> tuple[Optional[str], List[VariationMember]]:
    marketplace_id = marketplace_id_for_country(country)
    listing = client.get_listing(sku, countries=[country])
    parent_sku = extract_parent_sku(listing, marketplace_id)

    members: List[VariationMember] = []
    source_member = _member_from_item({**listing, "sku": sku}, marketplace_id)
    if source_member:
        members.append(source_member)

    if not parent_sku:
        return None, members

    for item in client.list_variation_children(parent_sku, countries=[country]):
        member = _member_from_item(item, marketplace_id)
        if member and member.sku not in {m.sku for m in members}:
            members.append(member)

    members.sort(key=lambda member: (member.units, member.sku))
    return parent_sku, members


def compute_linked_prices(
    source_sku: str,
    source_price: float,
    members: List[VariationMember],
    *,
    double_only: bool = False,
    exclude_skus: Optional[List[str]] = None,
) -> List[LinkedPriceUpdate]:
    excluded = {sku.upper() for sku in (exclude_skus or [])}
    source = next((member for member in members if member.sku == source_sku), None)
    if not source or source.units <= 0:
        return []

    updates: List[LinkedPriceUpdate] = []
    for member in members:
        if member.sku == source_sku or member.sku.upper() in excluded:
            continue
        if member.units <= source.units:
            continue

        ratio = member.units / source.units
        if abs(ratio - round(ratio)) > 1e-6:
            continue

        multiplier = int(round(ratio))
        if double_only and multiplier != 2:
            continue
        if not same_product_line(source, member):
            continue

        target_price = round(source_price * multiplier, 2)
        updates.append(
            LinkedPriceUpdate(
                sku=member.sku,
                units=member.units,
                current_price=member.current_price,
                target_price=target_price,
                multiplier=float(multiplier),
            )
        )

    updates.sort(key=lambda update: update.units)
    return updates

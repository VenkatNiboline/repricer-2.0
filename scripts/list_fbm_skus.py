#!/usr/bin/env python3
"""List all FBM SKUs in the seller catalog via SP-API."""

import argparse
import csv
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from amazon_listing import AmazonListingClient, MARKETPLACE_IDS
from fulfillment_pairs import classify_fulfillment, fba_sku_for, is_fbm_sku
from price import currency_for_country, extract_current_price, marketplace_id_for_country


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List FBM SKUs from live Amazon listings.")
    parser.add_argument("--country", default="DE", help="Marketplace country code (default: DE)")
    parser.add_argument("--region", default="EU", choices=["EU", "US", "FE"])
    parser.add_argument(
        "--suffix-only",
        action="store_true",
        help="Only include SKUs ending with FBM (used by the repricer auto-sync)",
    )
    parser.add_argument(
        "--csv",
        help="Optional path to write results as CSV",
    )
    return parser.parse_args()


def iter_all_listings(client: AmazonListingClient, country: str):
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


def main() -> int:
    args = parse_args()
    country = args.country.upper()
    if country not in MARKETPLACE_IDS:
        print(f"Error: unknown country '{country}'.")
        return 1

    marketplace_id = marketplace_id_for_country(country)
    currency = currency_for_country(country)

    client = AmazonListingClient(region=args.region)
    rows: List[dict] = []

    for item in iter_all_listings(client, country):
        sku = item.get("sku") or ""
        if not sku:
            continue

        fulfillment = classify_fulfillment(sku, item, marketplace_id)
        if fulfillment != "FBM":
            continue
        if args.suffix_only and not is_fbm_sku(sku):
            continue

        price = extract_current_price(item, marketplace_id)
        fba_pair = fba_sku_for(sku) if is_fbm_sku(sku) else ""
        rows.append(
            {
                "sku": sku,
                "fba_pair": fba_pair,
                "price": f"{price:.2f}" if price is not None else "",
                "currency": currency,
                "detected_by": "suffix" if is_fbm_sku(sku) else "fulfillment_channel",
            }
        )

    rows.sort(key=lambda row: row["sku"])

    print(f"Marketplace: {country} ({currency})")
    print(f"FBM SKUs:    {len(rows)}")
    if args.suffix_only:
        print("Filter:      suffix *FBM only (repricer-linked offers)")
    print("")
    print(f"{'SKU':<20} {'FBA pair':<16} {'Price':>10} {'Detected by'}")
    print("-" * 70)
    for row in rows:
        print(
            f"{row['sku']:<20} {row['fba_pair']:<16} "
            f"{(row['price'] + ' ' + currency) if row['price'] else 'N/A':>10} "
            f"{row['detected_by']}"
        )

    if args.csv:
        output = Path(args.csv)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["sku", "fba_pair", "price", "currency", "detected_by"],
            )
            writer.writeheader()
            writer.writerows(rows)
        print("")
        print(f"Wrote CSV: {output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

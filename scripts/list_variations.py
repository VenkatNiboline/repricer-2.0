#!/usr/bin/env python3
"""List variation siblings and linked price ratios for a SKU."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from amazon_listing import AmazonListingClient, MARKETPLACE_IDS
from fulfillment_pairs import DEFAULT_FBM_DISCOUNT, fbm_counterpart_exists, fbm_price_from_fba
from price import currency_for_country
from variations import compute_linked_prices, fetch_variation_family


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect parent/child variation pack sizes and linked prices."
    )
    parser.add_argument("--sku", required=True, help="Seller SKU")
    parser.add_argument("--country", default="DE", help="Marketplace country code")
    parser.add_argument("--region", default="EU", choices=["EU", "US", "FE"])
    parser.add_argument(
        "--price",
        type=float,
        help="Optional target price for the source SKU to preview linked prices",
    )
    parser.add_argument(
        "--double-only",
        action="store_true",
        help="Only show siblings with exactly 2x units",
    )
    parser.add_argument(
        "--fbm-discount",
        type=float,
        default=DEFAULT_FBM_DISCOUNT,
        help="FBM discount below FBA price as a decimal (default: 0.10 = 10%%)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    country = args.country.upper()
    if country not in MARKETPLACE_IDS:
        print(f"Error: unknown country '{country}'.")
        return 1

    currency = currency_for_country(country)

    try:
        client = AmazonListingClient(region=args.region)
        parent_sku, members = fetch_variation_family(client, args.sku, country)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    fbm_sku = fbm_counterpart_exists(client, args.sku, country)

    print(f"SKU:         {args.sku}")
    print(f"Marketplace: {country} ({currency})")
    print(f"Parent:      {parent_sku or 'none (standalone listing)'}")
    if fbm_sku:
        print(f"FBM pair:    {fbm_sku}")
    print("")
    print("Variation family:")
    for member in members:
        marker = " <-- source" if member.sku == args.sku else ""
        price = member.current_price
        price_text = f"{price:.2f}" if price is not None else "N/A"
        size = f" | size={member.size_label}" if member.size_label else ""
        print(
            f"  {member.sku:12} units={member.units:g} price={price_text}{size}{marker}"
        )

    if args.price is None:
        return 0

    print("")
    print(f"Linked prices if {args.sku} -> {args.price:.2f} {currency}:")
    linked = compute_linked_prices(
        args.sku,
        args.price,
        members,
        double_only=args.double_only,
    )
    if not linked:
        print("  (no linked siblings detected)")
        return 0

    for update in linked:
        current = f"{update.current_price:.2f}" if update.current_price is not None else "N/A"
        print(
            f"  {update.sku:12} units={update.units:g} "
            f"x{update.multiplier:g} -> {update.target_price:.2f} (current {current})"
        )

    if fbm_sku:
        fbm_target = fbm_price_from_fba(args.price, args.fbm_discount)
        print("")
        print(
            f"FBM linked price: {fbm_sku} -> {fbm_target:.2f} "
            f"({int(args.fbm_discount * 100)}% below FBA)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

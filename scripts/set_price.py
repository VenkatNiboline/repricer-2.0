#!/usr/bin/env python3
"""Set listing price via Amazon SP-API and verify the update."""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from amazon_listing import AmazonListingClient, MARKETPLACE_IDS
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
from variations import compute_linked_prices, fetch_variation_family


@dataclass
class UpdateResult:
    sku: str
    current_price: Optional[float]
    target_price: float
    validation_ok: bool
    pushed: bool
    submission_id: str
    status: str
    verified_price: Optional[float]
    error: Optional[str] = None
    linked: bool = False
    multiplier: Optional[float] = None
    link_kind: str = "primary"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update Amazon listing price for one SKU (and linked pack-size variations)."
    )
    parser.add_argument("--sku", required=True, help="Seller SKU (FBA SKU recommended)")
    parser.add_argument("--price", required=True, type=float, help="Target price")
    parser.add_argument(
        "--country",
        default="DE",
        help="Marketplace country code (default: DE)",
    )
    parser.add_argument(
        "--region",
        default="EU",
        choices=["EU", "US", "FE"],
        help="SP-API region (default: EU)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only; do not push live price update",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip read-back verification after push",
    )
    parser.add_argument(
        "--no-sync-siblings",
        action="store_true",
        help="Do not update larger pack-size variation siblings",
    )
    parser.add_argument(
        "--no-sync-fbm",
        action="store_true",
        help="Do not update the linked FBM SKU",
    )
    parser.add_argument(
        "--fbm-discount",
        type=float,
        default=DEFAULT_FBM_DISCOUNT,
        help="FBM discount below FBA price as a decimal (default: 0.10 = 10%%)",
    )
    parser.add_argument(
        "--double-only",
        action="store_true",
        help="When syncing siblings, only update packs with exactly 2x units",
    )
    parser.add_argument(
        "--exclude-sku",
        action="append",
        default=[],
        help="Sibling SKU to exclude from automatic sync (repeatable)",
    )
    parser.add_argument(
        "--verify-retries",
        type=int,
        default=3,
        help="Read-back attempts after push (default: 3)",
    )
    parser.add_argument(
        "--verify-delay",
        type=float,
        default=5.0,
        help="Seconds between read-back attempts (default: 5)",
    )
    return parser.parse_args()


def validate_patch(
    client: AmazonListingClient,
    sku: str,
    country: str,
    patches,
    product_type: str,
) -> None:
    result = client.patch_listing(
        sku=sku,
        patches=patches,
        product_type=product_type,
        countries=[country],
        mode="VALIDATION_PREVIEW",
    )
    status = result.get("status")
    if status != "VALID":
        issues = result.get("issues", [])
        raise RuntimeError(json.dumps(issues, indent=2))


def verify_price(
    client: AmazonListingClient,
    sku: str,
    country: str,
    marketplace_id: str,
    target_price: float,
    retries: int,
    delay: float,
) -> float:
    last_price = None
    for attempt in range(1, retries + 1):
        if attempt > 1:
            time.sleep(delay)
        listing = client.get_listing(sku, countries=[country])
        last_price = extract_current_price(listing, marketplace_id)
        if prices_match(last_price, target_price):
            return last_price
    raise RuntimeError(
        f"expected {target_price:.2f}, got {last_price if last_price is not None else 'N/A'}"
    )


def update_one_sku(
    client: AmazonListingClient,
    sku: str,
    target_price: float,
    country: str,
    marketplace_id: str,
    currency: str,
    *,
    dry_run: bool,
    verify: bool,
    verify_retries: int,
    verify_delay: float,
    linked: bool = False,
    multiplier: Optional[float] = None,
    link_kind: str = "primary",
) -> UpdateResult:
    listing = client.get_listing(sku, countries=[country])
    product_type = get_product_type(listing)
    if not product_type:
        return UpdateResult(
            sku=sku,
            current_price=None,
            target_price=target_price,
            validation_ok=False,
            pushed=False,
            submission_id="",
            status="",
            verified_price=None,
            error="could not determine productType",
            linked=linked,
            multiplier=multiplier,
            link_kind=link_kind,
        )

    current_price = extract_current_price(listing, marketplace_id)
    patches = build_price_patch(target_price, marketplace_id, currency)

    try:
        validate_patch(client, sku, country, patches, product_type)
    except Exception as exc:
        return UpdateResult(
            sku=sku,
            current_price=current_price,
            target_price=target_price,
            validation_ok=False,
            pushed=False,
            submission_id="",
            status="",
            verified_price=None,
            error=str(exc),
            linked=linked,
            multiplier=multiplier,
            link_kind=link_kind,
        )

    if dry_run:
        return UpdateResult(
            sku=sku,
            current_price=current_price,
            target_price=target_price,
            validation_ok=True,
            pushed=False,
            submission_id="",
            status="DRY_RUN",
            verified_price=None,
            linked=linked,
            multiplier=multiplier,
            link_kind=link_kind,
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
        return UpdateResult(
            sku=sku,
            current_price=current_price,
            target_price=target_price,
            validation_ok=True,
            pushed=False,
            submission_id="",
            status="",
            verified_price=None,
            error=str(exc),
            linked=linked,
            multiplier=multiplier,
            link_kind=link_kind,
        )

    submission_id = result.get("submissionId", "N/A")
    status = result.get("status", "N/A")
    verified_price = None
    error = None

    if verify:
        try:
            verified_price = verify_price(
                client,
                sku,
                country,
                marketplace_id,
                target_price,
                verify_retries,
                verify_delay,
            )
        except Exception as exc:
            error = str(exc)

    return UpdateResult(
        sku=sku,
        current_price=current_price,
        target_price=target_price,
        validation_ok=True,
        pushed=True,
        submission_id=submission_id,
        status=status,
        verified_price=verified_price,
        error=error,
        linked=linked,
        multiplier=multiplier,
        link_kind=link_kind,
    )


def print_result(result: UpdateResult, currency: str, fbm_discount: float) -> None:
    if result.link_kind == "fbm":
        label = "FBM SKU"
    elif result.link_kind == "variation":
        label = "Linked SKU"
    elif result.linked:
        label = "Linked SKU"
    else:
        label = "SKU"

    print(f"{label}:         {result.sku}")
    if result.link_kind == "fbm" and result.multiplier is not None:
        print(f"FBM rule:    {result.multiplier * 100:.0f}% of FBA ({int(fbm_discount * 100)}% off)")
    elif result.multiplier is not None:
        print(f"Multiplier:  x{result.multiplier:g}")

    current = result.current_price
    print(f"Current:     {current:.2f}" if current is not None else "Current:     N/A")
    print(f"Target:      {result.target_price:.2f} {currency}")

    if not result.validation_ok:
        print("Validation:  FAILED")
        if result.error:
            print(result.error)
        return

    print("Validation:  OK")
    if result.status == "DRY_RUN":
        print("Dry run:     no live update sent.")
        return

    if not result.pushed:
        print("Pushed:      FAILED")
        if result.error:
            print(result.error)
        return

    print(f"Pushed:      submissionId={result.submission_id}, status={result.status}")
    if result.verified_price is not None:
        print(f"Verified:    {result.verified_price:.2f} (matches target)")
    elif result.error:
        print("Verified:    FAILED")
        print(result.error)


def build_update_plan(
    args: argparse.Namespace,
    client: AmazonListingClient,
) -> tuple[Optional[str], List[PlannedUpdate]]:
    fba_sku, fba_price = normalize_fba_anchor(args.sku, args.price, args.fbm_discount)
    parent_sku, members = fetch_variation_family(client, fba_sku, args.country)

    plan: List[PlannedUpdate] = [
        PlannedUpdate(sku=fba_sku, target_price=fba_price, link_kind="primary")
    ]

    if not args.no_sync_siblings:
        linked_updates = compute_linked_prices(
            fba_sku,
            fba_price,
            members,
            double_only=args.double_only,
            exclude_skus=args.exclude_sku,
        )
        for update in linked_updates:
            plan.append(
                PlannedUpdate(
                    sku=update.sku,
                    target_price=update.target_price,
                    linked=True,
                    multiplier=update.multiplier,
                    link_kind="variation",
                )
            )

    if not args.no_sync_fbm:
        plan = append_fbm_updates(client, plan, args.country, args.fbm_discount)

    return parent_sku, plan


def main() -> int:
    args = parse_args()
    country = args.country.upper()

    if country not in MARKETPLACE_IDS:
        print(f"Error: unknown country '{country}'. Supported: {', '.join(sorted(MARKETPLACE_IDS))}")
        return 1

    if args.price <= 0:
        print("Error: price must be greater than zero.")
        return 1

    if args.fbm_discount < 0 or args.fbm_discount >= 1:
        print("Error: --fbm-discount must be between 0 and 1 (exclusive).")
        return 1

    currency = currency_for_country(country)
    marketplace_id = marketplace_id_for_country(country)
    verify = not args.no_verify

    try:
        client = AmazonListingClient(region=args.region)
        parent_sku, plan = build_update_plan(args, client)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    fba_sku, fba_price = normalize_fba_anchor(args.sku, args.price, args.fbm_discount)
    variation_count = sum(1 for update in plan if update.link_kind == "variation")
    fbm_count = sum(1 for update in plan if update.link_kind == "fbm")

    print(f"Marketplace: {country} ({currency})")
    if args.sku != fba_sku:
        print(f"Input SKU:   {args.sku} (converted to FBA anchor {fba_sku} @ {fba_price:.2f})")
    if parent_sku:
        print(f"Parent SKU:  {parent_sku}")
    if variation_count:
        print(f"Sync:        {variation_count} linked pack-size variation(s)")
    if fbm_count:
        print(f"FBM sync:    {fbm_count} FBM offer(s) at {int(args.fbm_discount * 100)}% below FBA")
    print("=" * 60)

    results: List[UpdateResult] = []
    exit_code = 0

    for index, planned in enumerate(plan):
        if index > 0:
            print("-" * 60)

        result = update_one_sku(
            client,
            planned.sku,
            planned.target_price,
            country,
            marketplace_id,
            currency,
            dry_run=args.dry_run,
            verify=verify,
            verify_retries=args.verify_retries,
            verify_delay=args.verify_delay,
            linked=planned.linked,
            multiplier=planned.multiplier,
            link_kind=planned.link_kind,
        )
        print_result(result, currency, args.fbm_discount)
        results.append(result)

        if not result.validation_ok or (not args.dry_run and not result.pushed):
            exit_code = 1
        elif result.pushed and verify and result.verified_price is None:
            exit_code = 2

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

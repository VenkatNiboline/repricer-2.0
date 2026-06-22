#!/usr/bin/env python3
"""Sync full SKU catalog from Amazon SP-API into local cache."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from catalog import catalog_stats, scan_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Amazon SKU catalog to local cache.")
    parser.add_argument("--country", default="DE", help="Marketplace country code")
    parser.add_argument("--region", default="EU", choices=["EU", "US", "FE"])
    parser.add_argument("--refresh", action="store_true", help="Force live scan from Amazon")
    args = parser.parse_args()

    print(f"Syncing catalog for {args.country} ({args.region})…")
    payload = scan_catalog(args.country, args.region, refresh=args.refresh)
    stats = catalog_stats(payload)

    print(json.dumps(stats, indent=2))
    print(f"Cached {stats['total']} SKUs (source: {stats['source']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

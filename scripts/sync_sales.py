#!/usr/bin/env python3
"""Backfill sales data from Amazon Sales & Traffic report."""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from amazon_reports import fetch_and_flatten_sales_report
from supabase_store import is_configured, upsert_sales_rows


def main():
    parser = argparse.ArgumentParser(description="Sync Amazon sales & traffic data")
    parser.add_argument("--country", default="DE")
    parser.add_argument("--region", default="EU")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    if not is_configured():
        print("Supabase not configured")
        sys.exit(1)

    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=max(1, args.days) - 1)
    print(f"Fetching {args.country} sales {start} to {end}…")
    rows = fetch_and_flatten_sales_report(args.country, start, end, region=args.region)
    count = upsert_sales_rows(rows)
    print(f"Upserted {count} rows")


if __name__ == "__main__":
    main()

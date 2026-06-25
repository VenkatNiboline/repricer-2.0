"""Amazon SP-API Reports client for GET_SALES_AND_TRAFFIC_REPORT."""

import gzip
import io
import json
import os
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from amazon_listing import SP_API_BASE_URLS
from get_access_token import get_access_token
from price import marketplace_id_for_country

REPORT_TYPE = "GET_SALES_AND_TRAFFIC_REPORT"
POLL_INTERVAL_SEC = 15
POLL_MAX_ATTEMPTS = 40


def _base_url(region: str = "EU") -> str:
    return SP_API_BASE_URLS.get(region, SP_API_BASE_URLS["EU"])


def _headers() -> Dict[str, str]:
    return {
        "x-amz-access-token": get_access_token(),
        "Content-Type": "application/json",
    }


def create_sales_traffic_report(
    country: str,
    start_date: date,
    end_date: date,
    region: str = "EU",
) -> str:
    marketplace_id = marketplace_id_for_country(country)
    payload = {
        "reportType": REPORT_TYPE,
        "marketplaceIds": [marketplace_id],
        "dataStartTime": f"{start_date.isoformat()}T00:00:00Z",
        "dataEndTime": f"{end_date.isoformat()}T23:59:59Z",
        "reportOptions": {
            "dateGranularity": "DAY",
            "asinGranularity": "CHILD",
        },
    }
    url = f"{_base_url(region)}/reports/2021-06-30/reports"
    response = requests.post(url, headers=_headers(), json=payload, timeout=60)
    response.raise_for_status()
    report_id = response.json().get("reportId")
    if not report_id:
        raise RuntimeError(f"No reportId in response: {response.text}")
    return report_id


def wait_for_report(report_id: str, region: str = "EU") -> str:
    url = f"{_base_url(region)}/reports/2021-06-30/reports/{report_id}"
    for _ in range(POLL_MAX_ATTEMPTS):
        response = requests.get(url, headers=_headers(), timeout=60)
        response.raise_for_status()
        data = response.json()
        status = data.get("processingStatus")
        if status == "DONE":
            document_id = data.get("reportDocumentId")
            if not document_id:
                raise RuntimeError("Report DONE but no reportDocumentId")
            return document_id
        if status in ("CANCELLED", "FATAL"):
            raise RuntimeError(f"Report failed with status {status}")
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(f"Report {report_id} not ready after polling")


def download_report_document(document_id: str, region: str = "EU") -> Dict[str, Any]:
    meta_url = f"{_base_url(region)}/reports/2021-06-30/documents/{document_id}"
    meta = requests.get(meta_url, headers=_headers(), timeout=60)
    meta.raise_for_status()
    meta_data = meta.json()
    download_url = meta_data.get("url")
    if not download_url:
        raise RuntimeError("No download URL for report document")

    raw = requests.get(download_url, timeout=120)
    raw.raise_for_status()
    content = raw.content
    if meta_data.get("compressionAlgorithm") == "GZIP":
        content = gzip.GzipFile(fileobj=io.BytesIO(content)).read()
    return json.loads(content.decode("utf-8"))


def _money(value: Any) -> tuple[Optional[float], Optional[str]]:
    if not value:
        return None, None
    if isinstance(value, dict):
        amount = value.get("amount")
        currency = value.get("currencyCode")
        return (float(amount) if amount is not None else None, currency)
    return None, None


def flatten_sales_traffic_report(
    report_json: Dict[str, Any],
    *,
    marketplace_id: str,
    seller_id: str,
    report_id: str,
    document_id: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    file_name = f"{REPORT_TYPE}_{report_id}.json"
    transaction_id = f"{report_id}_{document_id}"

    for item in report_json.get("salesAndTrafficByAsin") or []:
        sales = item.get("salesByAsin") or {}
        traffic = item.get("trafficByAsin") or {}
        amount, currency = _money(sales.get("orderedProductSales"))
        b2b_amount, b2b_currency = _money(sales.get("orderedProductSalesB2B"))

        ob_date = item.get("date")
        if not ob_date:
            continue

        rows.append(
            {
                "ob_marketplace_id": marketplace_id,
                "ob_seller_id": seller_id,
                "child_asin": item.get("childAsin") or item.get("asin"),
                "parent_asin": item.get("parentAsin"),
                "sku": item.get("sku"),
                "ordered_product_sales_amount": amount,
                "ordered_product_sales_currency_code": currency,
                "ordered_product_sales_b2_b_amount": b2b_amount,
                "ordered_product_sales_b2_b_currency_code": b2b_currency,
                "total_order_items": sales.get("totalOrderItems"),
                "total_order_items_b2_b": sales.get("totalOrderItemsB2B"),
                "units_ordered": sales.get("unitsOrdered"),
                "units_ordered_b2_b": sales.get("unitsOrderedB2B"),
                "browser_page_views": traffic.get("browserPageViews"),
                "browser_page_views_b2_b": traffic.get("browserPageViewsB2B"),
                "browser_page_views_percentage": traffic.get("browserPageViewsPercentage"),
                "browser_page_views_percentage_b2_b": traffic.get("browserPageViewsPercentageB2B"),
                "browser_session_percentage": traffic.get("browserSessionPercentage"),
                "browser_session_percentage_b2_b": traffic.get("browserSessionPercentageB2B"),
                "browser_sessions": traffic.get("browserSessions"),
                "browser_sessions_b2_b": traffic.get("browserSessionsB2B"),
                "buy_box_percentage": traffic.get("buyBoxPercentage"),
                "buy_box_percentage_b2_b": traffic.get("buyBoxPercentageB2B"),
                "mobile_app_page_views": traffic.get("mobileAppPageViews"),
                "mobile_app_page_views_b2_b": traffic.get("mobileAppPageViewsB2B"),
                "mobile_app_page_views_percentage": traffic.get("mobileAppPageViewsPercentage"),
                "mobile_app_page_views_percentage_b2_b": traffic.get(
                    "mobileAppPageViewsPercentageB2B"
                ),
                "mobile_app_session_percentage": traffic.get("mobileAppSessionPercentage"),
                "mobile_app_session_percentage_b2_b": traffic.get(
                    "mobileAppSessionPercentageB2B"
                ),
                "mobile_app_sessions": traffic.get("mobileAppSessions"),
                "mobile_app_sessions_b2_b": traffic.get("mobileAppSessionsB2B"),
                "page_views": traffic.get("pageViews"),
                "page_views_b2_b": traffic.get("pageViewsB2B"),
                "page_views_percentage": traffic.get("pageViewsPercentage"),
                "page_views_percentage_b2_b": traffic.get("pageViewsPercentageB2B"),
                "session_percentage": traffic.get("sessionPercentage"),
                "session_percentage_b2_b": traffic.get("sessionPercentageB2B"),
                "sessions": traffic.get("sessions"),
                "sessions_b2_b": traffic.get("sessionsB2B"),
                "unit_session_percentage": traffic.get("unitSessionPercentage"),
                "unit_session_percentage_b2_b": traffic.get("unitSessionPercentageB2B"),
                "ob_date": ob_date,
                "ob_transaction_id": transaction_id,
                "ob_file_name": file_name,
                "ob_processed_at": now_iso,
                "ob_modified_date": now_iso,
            }
        )
    return [r for r in rows if r.get("child_asin")]


def fetch_and_flatten_sales_report(
    country: str,
    start_date: date,
    end_date: date,
    region: str = "EU",
) -> List[Dict[str, Any]]:
    seller_id = os.getenv("SELLER_ID", "")
    marketplace_id = marketplace_id_for_country(country)
    report_id = create_sales_traffic_report(country, start_date, end_date, region=region)
    document_id = wait_for_report(report_id, region=region)
    report_json = download_report_document(document_id, region=region)
    return flatten_sales_traffic_report(
        report_json,
        marketplace_id=marketplace_id,
        seller_id=seller_id,
        report_id=report_id,
        document_id=document_id,
    )

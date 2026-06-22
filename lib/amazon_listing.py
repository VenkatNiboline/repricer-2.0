#!/usr/bin/env python3
"""Minimal Amazon Listings Items API client for price read/write."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

LIB_DIR = Path(__file__).parent
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import get_access_token

SCRIPT_DIR = Path(__file__).parent.parent
ENV_FILE = SCRIPT_DIR / "ENV" / "AmazonCredentials.env"

MARKETPLACE_IDS = {
    "US": "ATVPDKIKX0DER",
    "CA": "A2EUQ1WTGCTBG2",
    "MX": "A1AM78C64UM0Y8",
    "BR": "A2Q3Y263D00KWC",
    "IE": "A28R8C7NBKEWEA",
    "ES": "A1RKKUPIHCS9HS",
    "UK": "A1F83G8C2ARO7P",
    "FR": "A13V1IB3VIYZZH",
    "BE": "AMEN7PMS3EDWL",
    "NL": "A1805IZSGTT6HS",
    "DE": "A1PA6795UKMFR9",
    "IT": "APJ6JRA9NG5V4",
    "SE": "A2NODRKZP88ZB9",
    "ZA": "AE08WJ6YKNBMC",
    "PL": "A1C3SOZRARQ6R3",
    "EG": "ARBP9OOSHTCHU",
    "TR": "A33AVAJ2PDY3EV",
    "SA": "A17E79C6D8DWNP",
    "AE": "A2VIGQ35RCS4UG",
    "IN": "A21TJRUUN4KGV",
    "SG": "A19VAU5U5O7RUS",
    "AU": "A39IBJ37TRP1C6",
    "JP": "A1VC38T7YXB528",
}

SP_API_BASE_URLS = {
    "US": "https://sellingpartnerapi-na.amazon.com",
    "EU": "https://sellingpartnerapi-eu.amazon.com",
    "FE": "https://sellingpartnerapi-fe.amazon.com",
}


class AmazonListingClient:
    """Client for Listings Items GET/PATCH operations."""

    def __init__(self, region: str = "EU"):
        if not ENV_FILE.exists():
            raise FileNotFoundError(f"Credentials file not found: {ENV_FILE}")

        load_dotenv(ENV_FILE)
        self.seller_id = os.getenv("SELLER_ID")
        if not self.seller_id:
            raise ValueError("SELLER_ID not found in credentials file")

        self.access_token: Optional[str] = None
        self.region = region.upper()
        self.base_url = SP_API_BASE_URLS.get(self.region, SP_API_BASE_URLS["EU"])

    def _get_access_token(self) -> str:
        if not self.access_token:
            self.access_token = get_access_token.get_access_token()
        return self.access_token

    def _refresh_access_token(self) -> None:
        self.access_token = None
        self.access_token = get_access_token.get_access_token()

    def _make_request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.get("headers", {})
        if "x-amz-access-token" not in headers:
            headers["x-amz-access-token"] = self._get_access_token()
            kwargs["headers"] = headers

        response = requests.request(method, url, timeout=60, **kwargs)

        if response.status_code in (401, 403):
            error_data: Dict[str, Any] = {}
            try:
                error_data = response.json()
            except Exception:
                pass

            errors = error_data.get("errors", [{}])
            if errors:
                first_error = errors[0]
                error_message = str(first_error.get("message", "")).lower()
                error_details = str(first_error.get("details", "")).lower()
                error_code = str(first_error.get("code", "")).lower()
                token_keywords = ("token", "unauthorized", "expired", "access denied", "lwa")
                is_token_error = (
                    any(keyword in error_message for keyword in token_keywords)
                    or any(keyword in error_details for keyword in token_keywords)
                    or "unauthorized" in error_code
                )
                if is_token_error:
                    self._refresh_access_token()
                    kwargs["headers"]["x-amz-access-token"] = self.access_token
                    response = requests.request(method, url, timeout=60, **kwargs)

        return response

    def _get_headers(self) -> Dict[str, str]:
        return {
            "x-amz-access-token": self._get_access_token(),
            "Content-Type": "application/json",
        }

    def _get_marketplace_ids(self, countries: Optional[List[str]] = None) -> List[str]:
        if countries is None:
            return list(MARKETPLACE_IDS.values())

        marketplace_ids = []
        for country in countries:
            country_upper = country.upper()
            if country_upper not in MARKETPLACE_IDS:
                raise ValueError(f"Unknown country code: {country}")
            marketplace_ids.append(MARKETPLACE_IDS[country_upper])
        return marketplace_ids

    def get_listing(
        self,
        sku: str,
        marketplace_ids: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if marketplace_ids is None:
            marketplace_ids = self._get_marketplace_ids(countries)

        url = f"{self.base_url}/listings/2021-08-01/items/{self.seller_id}/{sku}"
        params = {
            "marketplaceIds": ",".join(marketplace_ids),
            "includedData": "summaries,attributes,offers,issues",
        }

        try:
            response = self._make_request_with_retry(
                "get", url, headers=self._get_headers(), params=params
            )
            if response.status_code == 200:
                return response.json()

            error_msg = f"Failed to fetch listing: HTTP {response.status_code}"
            try:
                error_msg += f"\n{json.dumps(response.json(), indent=2)}"
            except Exception:
                error_msg += f"\n{response.text}"
            raise Exception(error_msg)
        except requests.exceptions.RequestException as exc:
            raise Exception(f"Network error while fetching listing: {exc}") from exc

    def patch_listing(
        self,
        sku: str,
        patches: List[Dict[str, Any]],
        product_type: str,
        marketplace_ids: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        mode: Optional[str] = "VALIDATION_PREVIEW",
    ) -> Dict[str, Any]:
        if marketplace_ids is None:
            marketplace_ids = self._get_marketplace_ids(countries)

        url = f"{self.base_url}/listings/2021-08-01/items/{self.seller_id}/{sku}"
        params: Dict[str, str] = {"marketplaceIds": ",".join(marketplace_ids)}
        if mode:
            params["mode"] = mode

        payload = {"productType": product_type, "patches": patches}

        try:
            response = self._make_request_with_retry(
                "patch",
                url,
                headers=self._get_headers(),
                params=params,
                json=payload,
            )
            if response.status_code in (200, 202):
                return response.json()

            error_msg = f"Failed to update listing: HTTP {response.status_code}"
            try:
                error_msg += f"\n{json.dumps(response.json(), indent=2)}"
            except Exception:
                error_msg += f"\n{response.text}"
            raise Exception(error_msg)
        except requests.exceptions.RequestException as exc:
            raise Exception(f"Network error while updating listing: {exc}") from exc

    def search_listings_items(
        self,
        marketplace_ids: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        identifiers: Optional[List[str]] = None,
        identifiers_type: str = "SKU",
        variation_parent_sku: Optional[str] = None,
        included_data: str = "summaries,attributes,offers",
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        if marketplace_ids is None:
            marketplace_ids = self._get_marketplace_ids(countries)

        url = f"{self.base_url}/listings/2021-08-01/items/{self.seller_id}"
        params: Dict[str, Any] = {
            "marketplaceIds": marketplace_ids[0] if marketplace_ids else "",
            "includedData": included_data,
            "pageSize": min(page_size, 20),
        }

        if identifiers:
            params["identifiers"] = ",".join(identifiers[:20])
            params["identifiersType"] = identifiers_type
        if variation_parent_sku:
            params["variationParentSku"] = variation_parent_sku
        if page_token:
            params["pageToken"] = page_token

        try:
            response = self._make_request_with_retry(
                "get", url, headers=self._get_headers(), params=params
            )
            if response.status_code == 200:
                return response.json()

            error_msg = f"Failed to search listings: HTTP {response.status_code}"
            try:
                error_msg += f"\n{json.dumps(response.json(), indent=2)}"
            except Exception:
                error_msg += f"\n{response.text}"
            raise Exception(error_msg)
        except requests.exceptions.RequestException as exc:
            raise Exception(f"Network error while searching listings: {exc}") from exc

    def list_variation_children(
        self,
        parent_sku: str,
        countries: Optional[List[str]] = None,
        included_data: str = "summaries,attributes,offers",
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        while True:
            result = self.search_listings_items(
                countries=countries,
                variation_parent_sku=parent_sku,
                included_data=included_data,
                page_token=page_token,
            )
            items.extend(result.get("items") or [])
            pagination = result.get("pagination") or {}
            page_token = pagination.get("nextToken")
            if not page_token:
                break

        return items

#!/usr/bin/env python3
"""Access Token Generator for Amazon Selling Partner API (SP-API)."""

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

from env_config import load_env

SCRIPT_DIR = Path(__file__).parent.parent
ENV_FILE = SCRIPT_DIR / "ENV" / "AmazonCredentials.env"


def get_access_token(verbose: bool = False) -> str:
    """Load credentials and return a short-lived SP-API access token."""
    load_env()

    refresh_token = os.getenv("LWA_REFRESH_TOKEN")
    client_id = os.getenv("LWA_CLIENT_ID")
    client_secret = os.getenv("LWA_CLIENT_SECRET")

    missing = [
        name
        for name, value in [
            ("LWA_REFRESH_TOKEN", refresh_token),
            ("LWA_CLIENT_ID", client_id),
            ("LWA_CLIENT_SECRET", client_secret),
        ]
        if not value
    ]
    if missing:
        error_msg = f"Error: missing credentials in {ENV_FILE}: {', '.join(missing)}"
        if verbose:
            print(error_msg)
            sys.exit(1)
        raise ValueError(error_msg)

    token_url = "https://api.amazon.com/auth/o2/token"
    data = urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    )
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        if verbose:
            print("Generating access token...")
        response = requests.post(token_url, data=data, headers=headers, timeout=30)

        if response.status_code != 200:
            error_msg = f"Error retrieving access token: HTTP {response.status_code}"
            try:
                error_msg += f"\n{json.dumps(response.json(), indent=2)}"
            except Exception:
                error_msg += f"\n{response.text}"
            if verbose:
                print(error_msg)
                sys.exit(1)
            raise Exception(error_msg)

        result = response.json()
        access_token = result.get("access_token")
        if not access_token:
            error_msg = f"Error: access token missing in response: {result}"
            if verbose:
                print(error_msg)
                sys.exit(1)
            raise Exception(error_msg)

        if verbose:
            expires_in = result.get("expires_in", "N/A")
            print(f"Access token generated (expires in {expires_in}s).")
        return access_token

    except requests.exceptions.RequestException as exc:
        error_msg = f"Network error while retrieving access token: {exc}"
        if verbose:
            print(error_msg)
            sys.exit(1)
        raise Exception(error_msg) from exc


if __name__ == "__main__":
    token = get_access_token(verbose=True)
    print(token)

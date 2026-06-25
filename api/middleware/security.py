"""CSRF validation and distributed rate limiting."""

import logging
import os
import sys
from pathlib import Path
from typing import Callable

from fastapi import HTTPException, Request, Response

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from supabase_store import is_configured  # noqa: E402

logger = logging.getLogger(__name__)

CSRF_COOKIE = "repricer_csrf"
CSRF_HEADER = "x-csrf-token"
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

RATE_LIMITS = {
    "auth_login": (5, 900),
    "repricer": (30, 60),
    "sales_sync": (2, 3600),
    "default_mutate": (60, 60),
}


def _cookie_secure() -> bool:
    return os.getenv("VERCEL") == "1" or os.getenv("COOKIE_SECURE", "").lower() == "true"


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=False,
        secure=_cookie_secure(),
        samesite="strict",
        path="/",
        max_age=3600,
    )


def validate_csrf(request: Request) -> None:
    if request.method not in MUTATING_METHODS:
        return
    path = request.url.path
    if path.startswith("/api/auth/login") or path.startswith("/api/auth/signup"):
        return
    if path.endswith("/sync-cron") or path.endswith("/verify-pending-cron"):
        return

    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(403, "CSRF validation failed")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_group(path: str) -> str:
    if "/api/auth/login" in path:
        return "auth_login"
    if "/api/repricer/" in path:
        return "repricer"
    if "/api/sales/sync" in path:
        return "sales_sync"
    return "default_mutate"


def _rate_limit_allowed(rate_key: str, max_calls: int, window_sec: int) -> bool:
    if not is_configured():
        return True
    try:
        from supabase_store import get_client

        client = get_client(admin=True)
        result = client.rpc(
            "rate_limit_check",
            {
                "p_key": rate_key,
                "p_max": max_calls,
                "p_window_secs": window_sec,
            },
        ).execute()
        data = result.data
        if isinstance(data, bool):
            return data
        if isinstance(data, list) and data:
            return bool(data[0])
        return bool(data)
    except Exception:
        logger.exception("Rate limit check failed for key=%s; allowing request", rate_key)
        return True


def check_rate_limit(request: Request) -> None:
    if request.method not in MUTATING_METHODS:
        return
    client_ip = _client_ip(request)
    group = _rate_group(request.url.path)
    max_calls, window_sec = RATE_LIMITS.get(group, RATE_LIMITS["default_mutate"])
    rate_key = f"{client_ip}:{group}"
    if not _rate_limit_allowed(rate_key, max_calls, window_sec):
        raise HTTPException(429, "Rate limit exceeded")


async def security_middleware(request: Request, call_next: Callable):
    check_rate_limit(request)
    validate_csrf(request)
    return await call_next(request)

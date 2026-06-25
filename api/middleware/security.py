"""CSRF validation and simple rate limiting."""

import os
import time
from collections import defaultdict
from threading import Lock
from typing import Callable, Dict, List, Tuple

from fastapi import HTTPException, Request, Response

CSRF_COOKIE = "repricer_csrf"
CSRF_HEADER = "x-csrf-token"
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# In-memory rate limit buckets: (key, route_group) -> [timestamps]
_rate_lock = Lock()
_rate_buckets: Dict[Tuple[str, str], List[float]] = defaultdict(list)

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
    if path.endswith("/sync-cron"):
        return

    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(403, "CSRF validation failed")


def _rate_group(path: str) -> str:
    if "/api/auth/login" in path:
        return "auth_login"
    if "/api/repricer/" in path:
        return "repricer"
    if "/api/sales/sync" in path:
        return "sales_sync"
    return "default_mutate"


def check_rate_limit(request: Request) -> None:
    if request.method not in MUTATING_METHODS:
        return
    client_ip = request.client.host if request.client else "unknown"
    group = _rate_group(request.url.path)
    max_calls, window_sec = RATE_LIMITS.get(group, RATE_LIMITS["default_mutate"])
    key = (client_ip, group)
    now = time.time()
    cutoff = now - window_sec

    with _rate_lock:
        bucket = [t for t in _rate_buckets[key] if t > cutoff]
        if len(bucket) >= max_calls:
            raise HTTPException(429, "Rate limit exceeded")
        bucket.append(now)
        _rate_buckets[key] = bucket


async def security_middleware(request: Request, call_next: Callable):
    check_rate_limit(request)
    validate_csrf(request)
    return await call_next(request)

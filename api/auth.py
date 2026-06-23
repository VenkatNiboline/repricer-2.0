"""Server-side auth — httpOnly cookies and optional Bearer header."""

import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import Cookie, Header, HTTPException, Request

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from env_config import load_env

load_env()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

ACCESS_COOKIE = "repricer_at"
REFRESH_COOKIE = "repricer_rt"


def auth_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY)


def _token_from_request(
    authorization: Optional[str],
    access_cookie: Optional[str],
) -> Optional[str]:
    if access_cookie:
        return access_cookie
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip() or None
    return None


def get_current_user_id(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    repricer_at: Optional[str] = Cookie(default=None),
) -> Optional[str]:
    token = _token_from_request(authorization, repricer_at)
    if not token:
        return None
    if not auth_configured():
        return None
    try:
        from supabase import create_client

        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        response = client.auth.get_user(token)
        user = response.user
        return str(user.id) if user else None
    except Exception:
        return None


def require_user_id(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    repricer_at: Optional[str] = Cookie(default=None),
) -> str:
    if not auth_configured():
        return "local-dev"
    user_id = get_current_user_id(request, authorization, repricer_at)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id


def require_admin(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    repricer_at: Optional[str] = Cookie(default=None),
) -> str:
    if not auth_configured():
        return "local-dev"
    user_id = require_user_id(request, authorization, repricer_at)
    from supabase_store import get_profile

    profile = get_profile(user_id)
    if not profile or profile.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return user_id


def optional_user_id(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    repricer_at: Optional[str] = Cookie(default=None),
) -> Optional[str]:
    user_id = get_current_user_id(request, authorization, repricer_at)
    if auth_configured() and not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id

"""Server-side auth — httpOnly cookies and optional Bearer header."""

import os
import sys
from dataclasses import dataclass
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


def _validate_token(token: str) -> Optional[str]:
    """Return the user id for a valid access token, else None."""
    if not token or not auth_configured():
        return None
    try:
        from supabase import create_client

        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        response = client.auth.get_user(token)
        user = response.user
        return str(user.id) if user else None
    except Exception:
        return None


@dataclass
class AuthCtx:
    """Identity for a request. ``access_token`` is forwarded to the data layer so
    queries run under the caller's JWT and RLS policies are enforced."""

    user_id: Optional[str]
    access_token: Optional[str] = None

    @property
    def is_local_dev(self) -> bool:
        return self.user_id == "local-dev"


def get_current_user_id(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    repricer_at: Optional[str] = Cookie(default=None),
) -> Optional[str]:
    token = _token_from_request(authorization, repricer_at)
    if not token:
        return None
    return _validate_token(token)


def current_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    repricer_at: Optional[str] = Cookie(default=None),
) -> AuthCtx:
    """Resolve identity without enforcing it. Returns an empty context if unauthenticated."""
    token = _token_from_request(authorization, repricer_at)
    if not token or not auth_configured():
        return AuthCtx(None, None)
    user_id = _validate_token(token)
    return AuthCtx(user_id, token if user_id else None)


def require_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    repricer_at: Optional[str] = Cookie(default=None),
) -> AuthCtx:
    """Require a valid session. Forwards the token so reads/writes run under RLS."""
    if not auth_configured():
        return AuthCtx("local-dev", None)
    ctx = current_auth(request, authorization, repricer_at)
    if not ctx.user_id:
        raise HTTPException(401, "Authentication required")
    return ctx


def require_admin_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    repricer_at: Optional[str] = Cookie(default=None),
) -> AuthCtx:
    ctx = require_auth(request, authorization, repricer_at)
    if ctx.is_local_dev:
        return ctx
    from supabase_store import get_profile

    profile = get_profile(ctx.user_id, access_token=ctx.access_token)
    if not profile or profile.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return ctx


def require_user_id(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    repricer_at: Optional[str] = Cookie(default=None),
) -> str:
    return require_auth(request, authorization, repricer_at).user_id


def require_admin(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    repricer_at: Optional[str] = Cookie(default=None),
) -> str:
    return require_admin_auth(request, authorization, repricer_at).user_id


def optional_user_id(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    repricer_at: Optional[str] = Cookie(default=None),
) -> Optional[str]:
    user_id = get_current_user_id(request, authorization, repricer_at)
    if auth_configured() and not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id

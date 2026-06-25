"""BFF authentication — httpOnly cookie sessions."""

import secrets
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from api.auth import ACCESS_COOKIE, REFRESH_COOKIE, AuthCtx, auth_configured, current_auth
from api.middleware.security import set_csrf_cookie
from env_config import load_env

load_env()

import os

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

router = APIRouter()

ACCESS_MAX_AGE = 3600
REFRESH_MAX_AGE = 60 * 60 * 24 * 7


def _cookie_secure() -> bool:
    return os.getenv("VERCEL") == "1" or os.getenv("COOKIE_SECURE", "").lower() == "true"


def _auth_client():
    if not auth_configured():
        raise HTTPException(503, "Authentication not configured on server")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class SignUpIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: Optional[str] = None
    role: str = "user"


def _set_session_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    common = {
        "httponly": True,
        "secure": _cookie_secure(),
        "samesite": "strict",
        "path": "/",
    }
    response.set_cookie(ACCESS_COOKIE, access_token, max_age=ACCESS_MAX_AGE, **common)
    response.set_cookie(REFRESH_COOKIE, refresh_token, max_age=REFRESH_MAX_AGE, **common)


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


def _profile_for_user(
    user_id: str, email: Optional[str], access_token: Optional[str] = None
) -> UserOut:
    try:
        from supabase_store import get_profile

        profile = get_profile(user_id, access_token=access_token)
        if profile:
            return UserOut(
                id=user_id,
                email=profile.get("email") or email,
                role=profile.get("role") or "user",
            )
    except Exception:
        pass
    return UserOut(id=user_id, email=email, role="user")


@router.get("/auth/status")
def auth_status():
    return {"configured": auth_configured()}


@router.get("/auth/me", response_model=Optional[UserOut])
def auth_me(auth: AuthCtx = Depends(current_auth)):
    if not auth_configured() or not auth.user_id:
        return None
    try:
        from supabase_store import get_profile

        profile = get_profile(auth.user_id, access_token=auth.access_token)
        if profile:
            return UserOut(
                id=auth.user_id,
                email=profile.get("email"),
                role=profile.get("role") or "user",
            )
    except Exception:
        pass
    return UserOut(id=auth.user_id, role="user")


@router.get("/auth/csrf")
def issue_csrf(response: Response):
    token = secrets.token_urlsafe(32)
    set_csrf_cookie(response, token)
    return {"csrf_token": token}


@router.post("/auth/login", response_model=UserOut)
def login(body: LoginIn, response: Response):
    client = _auth_client()
    try:
        result = client.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as exc:
        raise HTTPException(401, "Invalid email or password") from exc

    session = result.session
    user = result.user
    if not session or not user:
        raise HTTPException(401, "Invalid email or password")

    _set_session_cookies(response, session.access_token, session.refresh_token)
    set_csrf_cookie(response, secrets.token_urlsafe(32))
    return _profile_for_user(str(user.id), user.email, access_token=session.access_token)


@router.post("/auth/signup")
def signup(body: SignUpIn, response: Response):
    client = _auth_client()
    try:
        result = client.auth.sign_up({"email": body.email, "password": body.password})
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    session = result.session
    user = result.user
    if session and user:
        _set_session_cookies(response, session.access_token, session.refresh_token)
        set_csrf_cookie(response, secrets.token_urlsafe(32))
        return _profile_for_user(str(user.id), user.email, access_token=session.access_token)

    return {"message": "Account created. Check your email if confirmation is required."}


@router.post("/auth/logout")
def logout(response: Response):
    _clear_session_cookies(response)
    return {"ok": True}

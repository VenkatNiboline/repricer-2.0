"""Optional Supabase auth helpers for API routes."""

import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import Header, HTTPException
from pathlib import Path

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / "ENV" / "AmazonCredentials.env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


def get_current_user_id(authorization: Optional[str] = Header(default=None)) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None

    token = authorization.removeprefix("Bearer ").strip()
    try:
        from supabase import create_client

        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        response = client.auth.get_user(token)
        user = response.user
        return str(user.id) if user else None
    except Exception:
        return None


def require_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    user_id = get_current_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id

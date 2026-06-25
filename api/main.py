#!/usr/bin/env python3
"""FastAPI server for the Amazon Repricer UI."""

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from api.middleware.security import security_middleware  # noqa: E402
from api.routes import auth, history, overview, qc, repricer, rules, sales, settings_db, skus, submissions  # noqa: E402
from api.auth import auth_configured  # noqa: E402
from env_config import amazon_api_enabled  # noqa: E402
from supabase_store import is_configured, is_readable  # noqa: E402

app = FastAPI(title="Amazon Repricer", version="2.1.0")

cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://repricer-2-0.vercel.app",
]
vercel_url = os.getenv("VERCEL_URL")
if vercel_url:
    cors_origins.append(f"https://{vercel_url}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://repricer-2-0-[a-z0-9-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await security_middleware(request, call_next)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if os.getenv("VERCEL") == "1":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(overview.router, prefix="/api", tags=["overview"])
app.include_router(skus.router, prefix="/api", tags=["skus"])
app.include_router(repricer.router, prefix="/api", tags=["repricer"])
app.include_router(rules.router, prefix="/api", tags=["rules"])
app.include_router(history.router, prefix="/api", tags=["history"])
app.include_router(submissions.router, prefix="/api", tags=["submissions"])
app.include_router(settings_db.router, prefix="/api", tags=["settings"])
app.include_router(qc.router, prefix="/api", tags=["qc"])
app.include_router(sales.router, prefix="/api", tags=["sales"])


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "auth_configured": auth_configured(),
        "amazon_api_enabled": amazon_api_enabled(),
        "history_write_ready": is_configured(),
        "db_configured": is_configured() or is_readable(),
        "db_write_ready": is_configured(),
    }

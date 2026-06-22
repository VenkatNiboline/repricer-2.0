#!/usr/bin/env python3
"""FastAPI server for the Amazon Repricer UI."""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from api.routes import history, repricer, rules, settings_db, skus  # noqa: E402

app = FastAPI(title="Amazon Repricer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(skus.router, prefix="/api", tags=["skus"])
app.include_router(repricer.router, prefix="/api", tags=["repricer"])
app.include_router(rules.router, prefix="/api", tags=["rules"])
app.include_router(history.router, prefix="/api", tags=["history"])
app.include_router(settings_db.router, prefix="/api", tags=["settings"])


@app.get("/api/health")
def health():
    return {"status": "ok"}

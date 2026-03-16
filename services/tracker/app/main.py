"""
CFTC Regulatory Ops Tracker — FastAPI Application
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
import secrets
from pathlib import Path

from app.config import CORS_ORIGINS, AUTH_USER, AUTH_PASS, UPLOAD_DIR
from app.db import get_connection
from app.schema import init_schema
from app.seed import seed_all

# Import routers
from app.routers import (
    organizations,
    people,
    matters,
    tasks,
    meetings,
    documents,
    decisions,
    updates,
    lookups,
    dashboard,
    tags,
)

logger = logging.getLogger(__name__)
security = HTTPBasic()


def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """HTTP Basic Auth dependency — validates credentials directly."""
    correct_user = secrets.compare_digest(credentials.username.encode(), AUTH_USER.encode())
    correct_pass = secrets.compare_digest(credentials.password.encode(), AUTH_PASS.encode())
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("Starting CFTC Tracker...")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        created = init_schema(conn)
        if created:
            logger.info(f"Schema: created {len(created)} new tables: {created}")
        seed_all(conn)
        logger.info("Database ready.")
    finally:
        conn.close()
    yield
    logger.info("Shutting down CFTC Tracker.")


app = FastAPI(
    title="CFTC Regulatory Ops Tracker",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers — all under /tracker/ prefix, all require auth
router_prefix = "/tracker"
app.include_router(dashboard.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(matters.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(tasks.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(people.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(organizations.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(meetings.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(documents.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(decisions.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(updates.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(lookups.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(tags.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])


@app.get("/tracker/health")
async def health():
    """Health check — no auth required."""
    return {"status": "ok", "service": "cftc-tracker", "version": "0.1.0"}

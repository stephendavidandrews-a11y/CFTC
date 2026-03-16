"""CFTC Comment Letter Analysis System - FastAPI Application (SQLite)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import get_connection
from app.core.schema import init_schema
from app.api.routes import router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

_db_available = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db_available
    logger.info("Starting CFTC Comment Analysis System (SQLite)...")
    try:
        conn = get_connection()
        try:
            created = init_schema(conn)
            if created:
                logger.info(f"Schema: created {len(created)} new tables")
            logger.info("Database ready.")
        finally:
            conn.close()
        _db_available = True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.warning("Starting in degraded mode — database unavailable")
        _db_available = False
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="CFTC Comment Letter Analysis System",
    description="Automated monitoring and analysis of public comment letters.",
    version="0.3.0 (SQLite)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def db_availability_middleware(request: Request, call_next):
    """Return 503 on API routes when database is unavailable."""
    if not _db_available and request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable. Service running in degraded mode."},
        )
    return await call_next(request)


app.include_router(router, prefix="/api/v1", tags=["CFTC Comment System"])


@app.get("/health")
async def health_check():
    """Health check with database connectivity test."""
    db_ok = False
    try:
        conn = get_connection()
        try:
            conn.execute("SELECT 1")
            db_ok = True
        finally:
            conn.close()
    except Exception:
        pass

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "version": "0.3.0",
        "database": "sqlite",
        "database_connected": db_ok,
    }

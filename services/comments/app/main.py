"""CFTC Comment Letter Analysis System - FastAPI Application (SQLite)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import get_connection
from app.core.schema import init_schema
from app.api.routes import router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CFTC Comment Analysis System (SQLite)...")
    conn = get_connection()
    try:
        created = init_schema(conn)
        if created:
            logger.info(f"Schema: created {len(created)} new tables")
        logger.info("Database ready.")
    finally:
        conn.close()
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="CFTC Comment Letter Analysis System",
    description="Automated monitoring and analysis of public comment letters.",
    version="0.2.0 (SQLite)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1", tags=["CFTC Comment System"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.2.0", "database": "sqlite"}

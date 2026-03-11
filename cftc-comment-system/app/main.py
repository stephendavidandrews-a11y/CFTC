"""CFTC Comment Letter Analysis System - FastAPI Application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api.routes import router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: create tables if they don't exist (dev convenience)
    logger.info("Starting CFTC Comment Analysis System...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified.")

    yield

    # Shutdown: close connections
    logger.info("Shutting down...")
    await engine.dispose()


app = FastAPI(
    title="CFTC Comment Letter Analysis System",
    description="Automated monitoring and analysis of public comment letters submitted to the CFTC during notice-and-comment rulemaking.",
    version="0.1.0 (Phase 1 - Core Infrastructure)",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router, prefix="/api/v1", tags=["CFTC Comment System"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0", "phase": "1 - Core Infrastructure"}

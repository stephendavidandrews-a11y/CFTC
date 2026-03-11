"""
FastAPI application entry point for the Network personal networking app.
Phase 1: CRUD operations. Phase 2: Sonnet AI intelligence. Phase 3: Auto-send scheduler.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import contacts, interactions, venues, happy_hours, intros, linkedin, outreach, ai
from app.routers import scheduler_router
from app.scheduler import start_scheduler, shutdown_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    init_db()
    start_scheduler()
    logger.info("Network app started with scheduler")
    yield
    # Shutdown
    shutdown_scheduler()
    logger.info("Network app shutdown complete")


app = FastAPI(
    title="Network",
    description="Personal networking app for managing contacts, interactions, happy hours, and outreach.",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS: allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(contacts.router, prefix="/api/contacts", tags=["Contacts"])
app.include_router(interactions.router, prefix="/api/interactions", tags=["Interactions"])
app.include_router(venues.router, prefix="/api/venues", tags=["Venues"])
app.include_router(happy_hours.router, prefix="/api/happy-hours", tags=["Happy Hours"])
app.include_router(intros.router, prefix="/api/intros", tags=["Intros"])
app.include_router(linkedin.router, prefix="/api/linkedin", tags=["LinkedIn Events"])
app.include_router(outreach.router, prefix="/api/outreach", tags=["Outreach Plans"])
app.include_router(ai.router, prefix="/api", tags=["AI Intelligence"])
app.include_router(scheduler_router.router, prefix="/api/scheduler", tags=["Scheduler"])


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": "Network", "version": "3.0.0", "phase": 3}


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}

"""
Work Management FastAPI sub-application.
Mounted into the main app under /api/v1/pipeline/work.
"""

import logging

from app.work.db import get_connection, attach_pipeline
from app.work.schema import init_work_schema
from app.work.seed import seed_all

logger = logging.getLogger(__name__)


def init_work_module():
    """Initialize work management DB schema and seed data. Called from main app lifespan."""
    conn = get_connection()
    try:
        created = init_work_schema(conn)
        if created:
            logger.info(f"Work schema: created {len(created)} new tables")
        seed_all(conn)
        logger.info("Work management database ready.")
    finally:
        conn.close()

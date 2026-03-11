"""
APScheduler integration for automated outreach generation.
Runs cron jobs that generate outreach plans and send push notifications.
"""

import asyncio
import logging
import sqlite3
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import DB_PATH
from app.services.outreach_service import (
    generate_thursday_plans,
    generate_professional_plans,
    check_due_contacts_and_generate,
    generate_happy_hour_invites,
    generate_happy_hour_reminders,
    check_professional_due,
)
from app.services.notify import notify_new_outreach

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone="US/Eastern")


def _get_db() -> sqlite3.Connection:
    """Get a direct DB connection for scheduler jobs (not using FastAPI DI)."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _log_job_run(db: sqlite3.Connection, job_name: str, title: str, message: str, plans_count: int):
    """Log a scheduler job run to the notification_log table."""
    db.execute(
        """
        INSERT INTO notification_log (job_name, sent_at, title, message, plans_generated)
        VALUES (?, ?, ?, ?, ?)
        """,
        [job_name, datetime.utcnow().isoformat(), title, message, plans_count],
    )
    db.commit()


# ── Job functions ─────────────────────────────────────────────────────

async def job_thursday_touchbase():
    """Generate Thursday social outreach and notify."""
    logger.info("Running job: thursday_touchbase")
    db = _get_db()
    try:
        result = await generate_thursday_plans(db, force=False)
        count = result.get("count", 0)
        if count > 0 and not result.get("existing"):
            await notify_new_outreach(count, "social_thursday")
            _log_job_run(db, "thursday_touchbase", f"Thursday Touchbase: {count} messages",
                        result.get("reasoning", ""), count)
        else:
            logger.info(f"Thursday touchbase: {result.get('reasoning', 'No new plans generated.')}")
    except Exception as e:
        logger.error(f"thursday_touchbase failed: {e}")
    finally:
        db.close()


async def job_happy_hour_invite():
    """Check for upcoming happy hours and generate invites (9 days before)."""
    logger.info("Running job: happy_hour_invite")
    db = _get_db()
    try:
        result = await generate_happy_hour_invites(db)
        count = result.get("count", 0)
        if count > 0:
            await notify_new_outreach(count, "happy_hour_invite")
            _log_job_run(db, "happy_hour_invite", f"Happy Hour Invites: {count} messages",
                        result.get("reasoning", ""), count)
        else:
            logger.info(f"HH invite: {result.get('reasoning', 'No happy hour to invite for.')}")
    except Exception as e:
        logger.error(f"happy_hour_invite failed: {e}")
    finally:
        db.close()


async def job_happy_hour_reminder():
    """Check for upcoming happy hours and generate reminders (2 days before)."""
    logger.info("Running job: happy_hour_reminder")
    db = _get_db()
    try:
        result = await generate_happy_hour_reminders(db)
        count = result.get("count", 0)
        if count > 0:
            await notify_new_outreach(count, "happy_hour_reminder")
            _log_job_run(db, "happy_hour_reminder", f"Happy Hour Reminders: {count} messages",
                        result.get("reasoning", ""), count)
        else:
            logger.info(f"HH reminder: {result.get('reasoning', 'No reminders needed.')}")
    except Exception as e:
        logger.error(f"happy_hour_reminder failed: {e}")
    finally:
        db.close()


async def job_professional_due():
    """Check professional contacts due for outreach and generate plans."""
    logger.info("Running job: professional_due")
    db = _get_db()
    try:
        result = await check_professional_due(db)
        count = result.get("count", 0)
        if count > 0:
            await notify_new_outreach(count, "professional_pulse")
            _log_job_run(db, "professional_due", f"Professional Due: {count} messages",
                        result.get("reasoning", ""), count)
        else:
            logger.info(f"Professional due: {result.get('reasoning', 'No contacts due.')}")
    except Exception as e:
        logger.error(f"professional_due failed: {e}")
    finally:
        db.close()


async def job_ad_hoc_due():
    """Check social contacts going cold and generate ad-hoc outreach."""
    logger.info("Running job: ad_hoc_due")
    db = _get_db()
    try:
        result = await check_due_contacts_and_generate(db)
        count = result.get("count", 0)
        if count > 0:
            await notify_new_outreach(count, "ad_hoc_due")
            _log_job_run(db, "ad_hoc_due", f"Due Contacts: {count} messages",
                        result.get("reasoning", ""), count)
        else:
            logger.info(f"Ad-hoc due: {result.get('reasoning', 'No contacts going cold.')}")
    except Exception as e:
        logger.error(f"ad_hoc_due failed: {e}")
    finally:
        db.close()


# ── Scheduler lifecycle ──────────────────────────────────────────────

def setup_jobs():
    """Register all scheduled jobs."""
    # Thursday Touchbase: Every Thursday at 8:00 AM ET
    scheduler.add_job(
        job_thursday_touchbase,
        CronTrigger(day_of_week="thu", hour=8, minute=0),
        id="thursday_touchbase",
        name="Thursday Social Touchbase",
        replace_existing=True,
    )

    # Happy Hour Invite: Every Sunday at 8:00 AM ET
    scheduler.add_job(
        job_happy_hour_invite,
        CronTrigger(day_of_week="sun", hour=8, minute=0),
        id="happy_hour_invite",
        name="Happy Hour Invites (9 days before)",
        replace_existing=True,
    )

    # Happy Hour Reminder: Every Sunday at 8:30 AM ET
    scheduler.add_job(
        job_happy_hour_reminder,
        CronTrigger(day_of_week="sun", hour=8, minute=30),
        id="happy_hour_reminder",
        name="Happy Hour Reminders (2 days before)",
        replace_existing=True,
    )

    # Professional Due: Every Monday at 8:00 AM ET
    scheduler.add_job(
        job_professional_due,
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="professional_due",
        name="Professional Contacts Due Check",
        replace_existing=True,
    )

    # Ad-Hoc Due: Every day at 9:00 AM ET
    scheduler.add_job(
        job_ad_hoc_due,
        CronTrigger(hour=9, minute=0),
        id="ad_hoc_due",
        name="Daily Cold Contact Check",
        replace_existing=True,
    )


def start_scheduler():
    """Initialize and start the scheduler."""
    setup_jobs()
    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def shutdown_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")


async def trigger_job(job_id: str) -> dict:
    """Manually trigger a scheduler job for testing."""
    job_map = {
        "thursday_touchbase": job_thursday_touchbase,
        "happy_hour_invite": job_happy_hour_invite,
        "happy_hour_reminder": job_happy_hour_reminder,
        "professional_due": job_professional_due,
        "ad_hoc_due": job_ad_hoc_due,
    }

    job_fn = job_map.get(job_id)
    if not job_fn:
        return {"error": f"Unknown job: {job_id}"}

    try:
        await job_fn()
        return {"status": "completed", "job": job_id}
    except Exception as e:
        return {"status": "error", "job": job_id, "error": str(e)}

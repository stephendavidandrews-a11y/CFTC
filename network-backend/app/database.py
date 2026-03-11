"""
SQLite database connection and table initialization for the Network app.
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(os.environ.get("NETWORK_DB_PATH", str(Path(__file__).resolve().parent.parent / "network.db")))


def get_db():
    """Yield a database connection with row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            how_we_met TEXT,
            current_role TEXT,
            domain TEXT,
            tier TEXT NOT NULL DEFAULT 'New',
            is_super_connector BOOLEAN DEFAULT 0,
            relationship_status TEXT,
            interests TEXT,
            their_goals TEXT,
            what_i_offer TEXT,
            activity_prefs TEXT,
            last_contact_date DATE,
            next_action TEXT,
            notes TEXT,
            linkedin_url TEXT,
            linkedin_headline TEXT,
            linkedin_last_checked DATE,
            created_at DATETIME DEFAULT (datetime('now')),
            updated_at DATETIME DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL,
            date DATE NOT NULL,
            type TEXT NOT NULL,
            who_initiated TEXT,
            summary TEXT,
            open_loops TEXT,
            follow_up_date DATE,
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS outreach_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_of DATE NOT NULL,
            contact_id INTEGER NOT NULL,
            message_draft TEXT NOT NULL,
            reasoning TEXT,
            message_type TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            sent_at DATETIME,
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS happy_hours (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            venue_id INTEGER,
            theme TEXT,
            sonnet_reasoning TEXT,
            FOREIGN KEY (venue_id) REFERENCES venues(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS happy_hour_attendees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            happy_hour_id INTEGER NOT NULL,
            contact_id INTEGER NOT NULL,
            role TEXT,
            rsvp_status TEXT NOT NULL DEFAULT 'invited',
            brought_guest BOOLEAN DEFAULT 0,
            FOREIGN KEY (happy_hour_id) REFERENCES happy_hours(id) ON DELETE CASCADE,
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT,
            neighborhood TEXT,
            vibe TEXT,
            best_for TEXT,
            price_range TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS intros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_a_id INTEGER NOT NULL,
            person_b_id INTEGER NOT NULL,
            date DATE NOT NULL,
            context TEXT,
            outcome TEXT,
            FOREIGN KEY (person_a_id) REFERENCES contacts(id) ON DELETE CASCADE,
            FOREIGN KEY (person_b_id) REFERENCES contacts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS linkedin_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL,
            detected_date DATE NOT NULL,
            event_type TEXT NOT NULL,
            significance TEXT NOT NULL DEFAULT 'medium',
            description TEXT NOT NULL,
            outreach_hook TEXT,
            opportunity_flag TEXT,
            used_in_outreach BOOLEAN DEFAULT 0,
            dismissed BOOLEAN DEFAULT 0,
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
        );

        -- Indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_contacts_tier ON contacts(tier);
        CREATE INDEX IF NOT EXISTS idx_contacts_domain ON contacts(domain);
        CREATE INDEX IF NOT EXISTS idx_contacts_last_contact ON contacts(last_contact_date);
        CREATE INDEX IF NOT EXISTS idx_interactions_contact ON interactions(contact_id);
        CREATE INDEX IF NOT EXISTS idx_interactions_date ON interactions(date);
        CREATE INDEX IF NOT EXISTS idx_outreach_week ON outreach_plans(week_of);
        CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_plans(status);
        CREATE INDEX IF NOT EXISTS idx_hh_attendees_hh ON happy_hour_attendees(happy_hour_id);
        CREATE INDEX IF NOT EXISTS idx_linkedin_contact ON linkedin_events(contact_id);
        CREATE INDEX IF NOT EXISTS idx_linkedin_dismissed ON linkedin_events(dismissed);
    """)

    # ── v2 migration: add professional contacts columns ──────────────
    # Use try/except because ALTER TABLE ADD COLUMN errors if column already exists in SQLite.
    migrations = [
        "ALTER TABLE contacts ADD COLUMN contact_type TEXT DEFAULT 'social'",
        "ALTER TABLE contacts ADD COLUMN professional_tier TEXT",
        "ALTER TABLE outreach_plans ADD COLUMN plan_type TEXT DEFAULT 'social_thursday'",
    ]
    for stmt in migrations:
        try:
            cursor.execute(stmt)
        except sqlite3.OperationalError:
            pass  # Column already exists — safe to ignore

    # v2 indexes (IF NOT EXISTS is safe to run repeatedly)
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type);
        CREATE INDEX IF NOT EXISTS idx_contacts_pro_tier ON contacts(professional_tier);
        CREATE INDEX IF NOT EXISTS idx_outreach_plan_type ON outreach_plans(plan_type);
    """)

    # ── v3 migration: scheduler / notification tables ──────────────────
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            sent_at DATETIME NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            plans_generated INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_notif_log_sent ON notification_log(sent_at);
    """)

    # v2.1 data migration: normalize professional_tier values to human-readable form.
    # Old values: tier_1_monthly, tier_2_6week, tier_3_quarterly
    # New values: Tier 1, Tier 2, Tier 3
    tier_renames = {
        "tier_1_monthly": "Tier 1",
        "tier_2_6week": "Tier 2",
        "tier_3_quarterly": "Tier 3",
    }
    for old_val, new_val in tier_renames.items():
        cursor.execute(
            "UPDATE contacts SET professional_tier = ? WHERE professional_tier = ?",
            [new_val, old_val],
        )

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

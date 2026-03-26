"""
CFTC Regulatory Ops Tracker — Seed Data

Seeds CFTC organizational structure and personnel from cftc.gov/Contact.
Matters come from the pipeline sync — no demo matters seeded here.
Idempotent: checks if organizations table already has rows before inserting.
"""

import sqlite3
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _uid() -> str:
    return str(uuid.uuid4())


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def seed_all(conn: sqlite3.Connection) -> None:
    """Seed all data. Skips entirely if organizations already has rows."""
    cursor = conn.cursor()

    row = cursor.execute("SELECT COUNT(*) FROM organizations").fetchone()
    if row[0] > 0:
        logger.info(
            "Seed skipped — organizations table already has data (%d rows).", row[0]
        )
        return

    now = _iso(datetime.utcnow())

    # ------------------------------------------------------------------
    # 1. Organizations — real CFTC structure from cftc.gov/Contact
    # ------------------------------------------------------------------
    # Build CFTC parent ID first so children can reference it
    cftc_id = _uid()

    orgs = {
        # CFTC HQ (top-level parent)
        "cftc": (
            cftc_id,
            "Commodity Futures Trading Commission",
            "CFTC",
            "CFTC office",
            None,
        ),
        # Chairman & Commissioners — child of CFTC
        "chairman": (
            _uid(),
            "Office of Chairman Selig",
            None,
            "Commissioner office",
            cftc_id,
        ),
        # Divisions — all children of CFTC
        "ogc": (_uid(), "Office of the General Counsel", "OGC", "CFTC office", cftc_id),
        "dcr": (
            _uid(),
            "Division of Clearing and Risk",
            "DCR",
            "CFTC division",
            cftc_id,
        ),
        "doe": (_uid(), "Division of Enforcement", "DOE", "CFTC division", cftc_id),
        "dmo": (
            _uid(),
            "Division of Market Oversight",
            "DMO",
            "CFTC division",
            cftc_id,
        ),
        "mpd": (
            _uid(),
            "Market Participants Division",
            "MPD",
            "CFTC division",
            cftc_id,
        ),
        "dod": (_uid(), "Division of Data", "DOD", "CFTC division", cftc_id),
        "doa": (_uid(), "Division of Administration", "DOA", "CFTC division", cftc_id),
        # Offices — all children of CFTC
        "oia": (
            _uid(),
            "Office of International Affairs",
            "OIA",
            "CFTC office",
            cftc_id,
        ),
        "opa": (_uid(), "Office of Public Affairs", "OPA", "CFTC office", cftc_id),
        "olia": (
            _uid(),
            "Office of Legislative and Intergovernmental Affairs",
            "OLIA",
            "CFTC office",
            cftc_id,
        ),
        "oceo": (
            _uid(),
            "Office of Customer Education and Outreach",
            "OCEO",
            "CFTC office",
            cftc_id,
        ),
        "oig": (
            _uid(),
            "Office of the Inspector General",
            "OIG",
            "CFTC office",
            cftc_id,
        ),
        # External agencies (no parent)
        "sec": (
            _uid(),
            "Securities and Exchange Commission",
            "SEC",
            "Federal agency",
            None,
        ),
        "treasury": (
            _uid(),
            "Department of the Treasury",
            "Treasury",
            "Federal agency",
            None,
        ),
        "omb": (
            _uid(),
            "Office of Management and Budget",
            "OMB",
            "White House / OMB",
            None,
        ),
        # Exchanges / industry (no parent)
        "cme": (_uid(), "CME Group", "CME", "Exchange", None),
        "ice": (_uid(), "Intercontinental Exchange", "ICE", "Exchange", None),
        "fia": (
            _uid(),
            "Futures Industry Association",
            "FIA",
            "Trade association",
            None,
        ),
    }

    for key, (oid, name, short, otype, parent) in orgs.items():
        cursor.execute(
            """INSERT INTO organizations (id, name, short_name, organization_type,
               parent_organization_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (oid, name, short, otype, parent, now, now),
        )

    # ------------------------------------------------------------------
    # 2. People — real CFTC personnel from cftc.gov/Contact
    # ------------------------------------------------------------------
    people = {}

    def _person(
        key,
        full_name,
        first,
        last,
        title,
        org_key,
        phone=None,
        rel_cat=None,
        team_workload=0,
        manager_key=None,
    ):
        people[key] = _uid()
        cursor.execute(
            """INSERT INTO people
               (id, full_name, first_name, last_name, title, organization_id,
                phone, relationship_category,
                include_in_team_workload, manager_person_id,
                is_active, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'import', ?, ?)""",
            (
                people[key],
                full_name,
                first,
                last,
                title,
                orgs[org_key][0],
                phone,
                rel_cat,
                team_workload,
                people.get(manager_key),
                now,
                now,
            ),
        )

    # --- Chairman's Office ---
    _person(
        "selig",
        "Michael S. Selig",
        "Michael",
        "Selig",
        "Chairman",
        "chairman",
        "202-418-5128",
        "Boss",
    )
    _person(
        "zaidi",
        "Amir Zaidi",
        "Amir",
        "Zaidi",
        "Chief of Staff",
        "chairman",
        "202-418-5128",
        "Boss",
    )
    _person(
        "titus",
        "Alex Titus",
        "Alex",
        "Titus",
        "Chief Advisor",
        "chairman",
        "202-418-5128",
        "Leadership",
    )
    _person(
        "tente",
        "Meghan Tente",
        "Meghan",
        "Tente",
        "Senior Advisor",
        "chairman",
        "202-418-5128",
        "Leadership",
    )
    _person(
        "passalacqua",
        "Michael Passalacqua",
        "Michael",
        "Passalacqua",
        "Senior Advisor",
        "chairman",
        "202-418-5128",
        "Leadership",
    )
    _person(
        "mitchell",
        "Cal Mitchell",
        "Cal",
        "Mitchell",
        "Senior Advisor",
        "chairman",
        "202-418-5128",
        "Leadership",
    )
    _person(
        "weyls",
        "Brigitte Weyls",
        "Brigitte",
        "Weyls",
        "Senior Advisor",
        "chairman",
        "202-418-5128",
        "Leadership",
    )
    _person(
        "mastrogiacomo",
        "Elizabeth Mastrogiacomo",
        "Elizabeth",
        "Mastrogiacomo",
        "Senior Advisor",
        "chairman",
        "202-418-5128",
        "Leadership",
    )
    _person(
        "johnston_e",
        "Emma Johnston",
        "Emma",
        "Johnston",
        "Senior Agriculture Advisor",
        "chairman",
        "202-418-5128",
        "Leadership",
    )
    _person(
        "gunewardena",
        "Mel Gunewardena",
        "Mel",
        "Gunewardena",
        "Senior Markets Advisor / Director OIA",
        "oia",
        "202-418-5645",
        "Leadership",
    )

    # --- Office of the General Counsel ---
    _person(
        "badgley",
        "Tyler S. Badgley",
        "Tyler",
        "Badgley",
        "General Counsel",
        "ogc",
        "202-418-5000",
        "Boss",
    )
    _person(
        "einstman",
        "John Einstman",
        "John",
        "Einstman",
        "Deputy General Counsel, General Law",
        "ogc",
        None,
        "Leadership",
        team_workload=1,
        manager_key="badgley",
    )
    _person(
        "stukes",
        "Anne Stukes",
        "Anne",
        "Stukes",
        "Acting Deputy General Counsel (Litigation, Enforcement & Adjudication)",
        "ogc",
        None,
        "Leadership",
        team_workload=1,
        manager_key="badgley",
    )
    _person(
        "robinson",
        "Natasha Robinson",
        "Natasha",
        "Robinson",
        "Deputy General Counsel, Legislative & Intergovernmental Affairs",
        "ogc",
        None,
        "Leadership",
        team_workload=1,
        manager_key="badgley",
    )
    _person(
        "jurgens",
        "Melissa Jurgens",
        "Melissa",
        "Jurgens",
        "Deputy General Counsel, Secretariat and Information Management",
        "ogc",
        None,
        "Leadership",
        team_workload=1,
        manager_key="badgley",
    )
    _person(
        "kirkpatrick",
        "Christopher J. Kirkpatrick",
        "Christopher",
        "Kirkpatrick",
        "Secretary of the Commission",
        "ogc",
        "202-418-5000",
        "OGC peer",
    )
    _person(
        "smith_e",
        "Eugene Smith",
        "Eugene",
        "Smith",
        "Director, Office of Proceedings",
        "ogc",
        "202-418-5000",
        "OGC peer",
    )

    # --- Division of Clearing and Risk ---
    _person(
        "haynes",
        "Richard Haynes",
        "Richard",
        "Haynes",
        "Acting Director",
        "dcr",
        "202-418-5430",
        "Internal client",
    )
    _person(
        "josephson",
        "Sarah Josephson",
        "Sarah",
        "Josephson",
        "Deputy Director, International & Domestic Clearing Initiatives",
        "dcr",
        None,
        "Internal client",
    )
    _person(
        "donovan",
        "Eileen Donovan",
        "Eileen",
        "Donovan",
        "Deputy Director, Clearing Policy",
        "dcr",
        None,
        "Internal client",
    )

    # --- Division of Enforcement ---
    _person(
        "miller",
        "David I. Miller",
        "David",
        "Miller",
        "Director",
        "doe",
        "202-418-5000",
        "Internal client",
    )
    _person(
        "hayeck",
        "Paul Hayeck",
        "Paul",
        "Hayeck",
        "Deputy Director",
        "doe",
        None,
        "Internal client",
    )

    # --- Division of Market Oversight ---
    _person(
        "fisanich",
        "Frank Fisanich",
        "Frank",
        "Fisanich",
        "Acting Director",
        "dmo",
        "202-418-5000",
        "Internal client",
    )
    _person(
        "varma",
        "Rahul Varma",
        "Rahul",
        "Varma",
        "Deputy Director, Products and Market Analytics Branch",
        "dmo",
        None,
        "Internal client",
    )

    # --- Market Participants Division ---
    _person(
        "smith_t",
        "Thomas Smith",
        "Thomas",
        "Smith",
        "Acting Director",
        "mpd",
        "202-418-5000",
        "Internal client",
    )

    # --- Division of Data ---
    _person(
        "wehner",
        "Ed Wehner",
        "Ed",
        "Wehner",
        "Chief Data Officer and Director",
        "dod",
        "202-418-5000",
        "Internal client",
    )

    # --- Division of Administration ---
    _person(
        "sielski",
        "Marc H. Sielski",
        "Marc",
        "Sielski",
        "Executive Director",
        "doa",
        "202-418-5000",
        "Internal client",
    )
    _person(
        "perera",
        "Janaka Perera",
        "Janaka",
        "Perera",
        "Chief Information Officer",
        "doa",
        None,
        "Internal client",
    )

    # --- Office of International Affairs ---
    _person(
        "melara",
        "Mauricio Melara",
        "Mauricio",
        "Melara",
        "Deputy Director",
        "oia",
        None,
        "OGC peer",
    )

    # --- Office of Public Affairs ---
    _person(
        "nethercott",
        "Brooke Nethercott",
        "Brooke",
        "Nethercott",
        "Director",
        "opa",
        "202-418-5080",
        "OGC peer",
    )

    # --- Office of Legislative Affairs ---
    _person(
        "brubaker",
        "Alan Brubaker",
        "Alan",
        "Brubaker",
        "Director",
        "olia",
        "202-418-5764",
        "OGC peer",
    )

    # --- Office of Inspector General ---
    _person(
        "skinner",
        "Christopher Skinner",
        "Christopher",
        "Skinner",
        "Inspector General",
        "oig",
        "202-418-5510",
        "Internal client",
    )

    # --- External (for stakeholder demos) ---
    # These are fictional — external contacts for demo matters
    _person(
        "sec_contact",
        "Jennifer Walsh",
        "Jennifer",
        "Walsh",
        "Deputy Director, Division of Trading and Markets",
        "sec",
        None,
        "Partner agency",
    )
    _person(
        "treasury_contact",
        "Robert Chen",
        "Robert",
        "Chen",
        "Deputy Assistant Secretary, Financial Markets",
        "treasury",
        None,
        "Partner agency",
    )
    _person(
        "cme_contact",
        "Margaret Liu",
        "Margaret",
        "Liu",
        "SVP, Regulatory Affairs",
        "cme",
        None,
        "Outside party",
    )
    _person(
        "fia_contact",
        "James Henderson",
        "James",
        "Henderson",
        "VP, Regulatory Policy",
        "fia",
        None,
        "Outside party",
    )

    conn.commit()
    logger.info(
        "Seed complete — %d orgs, %d people. Matters will be created by pipeline sync.",
        len(orgs),
        len(people),
    )


def seed_schema_v2_defaults(conn: sqlite3.Connection) -> None:
    """Seed staleness_config and matter_number_seq. Idempotent."""
    cursor = conn.cursor()

    # ── staleness_config ──
    # Check if table exists and has rows
    try:
        row = cursor.execute("SELECT COUNT(*) FROM staleness_config").fetchone()
        if row[0] == 0:
            defaults = [
                ("sc-rm-default",  "rulemaking",     None,               30,  60,  "Default for rulemakings"),
                ("sc-rm-comment",  "rulemaking",     "comment_analysis", 90,  120, "Comment analysis takes time"),
                ("sc-gd-default",  "guidance",       None,               14,  30,  "Guidance matters move faster"),
                ("sc-en-default",  "enforcement",    None,               7,   14,  "Enforcement has tight timelines"),
                ("sc-cg-default",  "congressional",  None,               3,   7,   "Congressional responses are urgent"),
                ("sc-br-default",  "briefing",       None,               7,   14,  "Briefing prep is time-bound"),
                ("sc-ad-default",  "administrative", None,               30,  60,  "Admin matters are lower urgency"),
                ("sc-iq-default",  "inquiry",        None,               14,  30,  "Industry inquiries need timely response"),
                ("sc-ot-default",  "other",          None,               21,  45,  "Default for uncategorized"),
            ]
            cursor.executemany(
                "INSERT OR IGNORE INTO staleness_config (id, matter_type, workflow_status, stale_days, critical_stale_days, description) VALUES (?, ?, ?, ?, ?, ?)",
                defaults,
            )
            conn.commit()
            logger.info("Seeded %d staleness_config defaults", len(defaults))
    except Exception:
        pass  # Table doesn't exist yet (pre-migration v5)

    # ── matter_number_seq ──
    try:
        row = cursor.execute("SELECT COUNT(*) FROM matter_number_seq").fetchone()
        if row[0] == 0:
            # Initialize from existing matter_number values
            rows = cursor.execute(
                "SELECT CAST(SUBSTR(matter_number, 5, 4) AS INTEGER) AS yr, "
                "MAX(CAST(SUBSTR(matter_number, 10) AS INTEGER)) AS max_seq "
                "FROM matters WHERE matter_number LIKE 'MAT-%' GROUP BY yr"
            ).fetchall()
            for yr_row in rows:
                cursor.execute(
                    "INSERT OR IGNORE INTO matter_number_seq (prefix, year, next_val) VALUES ('MAT', ?, ?)",
                    (yr_row[0], yr_row[1] + 1),
                )
            if not rows:
                # No existing matters — seed current year starting at 1
                from datetime import datetime as dt
                cursor.execute(
                    "INSERT OR IGNORE INTO matter_number_seq (prefix, year, next_val) VALUES ('MAT', ?, 1)",
                    (dt.now().year,),
                )
            conn.commit()
            logger.info("Seeded matter_number_seq from %d year(s) of existing data", len(rows) if rows else 1)
    except Exception:
        pass  # Table doesn't exist yet

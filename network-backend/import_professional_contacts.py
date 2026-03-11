"""
Import 44 professional contacts (from the Excel v2 "Professional Contacts" sheet)
into the Network SQLite database.

Handles:
- Adding contact_type / professional_tier columns if they don't exist yet
- Duplicate detection by name (skips contacts already in DB)
- Phone number formatting (integers -> strings, strip whitespace)
- Treating warning-prefixed values as NULL

Usage: python import_professional_contacts.py
"""
import sqlite3
import os
import re
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "network.db")


def format_phone(raw):
    """
    Normalize phone numbers:
    - Convert integers to strings
    - Strip whitespace
    - Format bare 10-digit numbers as XXX-XXX-XXXX
    - Return None for None / warning-prefixed values
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.startswith("\u26a0"):
        return None
    # If it's a bare 10-digit number, format it
    digits = re.sub(r"\D", "", s)
    if len(digits) == 10 and re.match(r"^\d+$", s):
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return s


def clean_value(val):
    """Return None for warning-prefixed or empty values."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.startswith("\u26a0"):
        return None
    return s


# ── 44 unique professional contacts ──────────────────────────────────────
# Duplicates removed:
#   - Brianna Sacks (row 38 journalist dup) -- merged into row 11 with Media/Press domain
#   - Charlie Albus (row 40) -- already exists as social contact
#   - David Simons (row 41 private companies dup) -- already imported at row 15
#   - Maxwell Pritt (row 45 private companies dup) -- already imported at row 29

PROFESSIONAL_CONTACTS = [
    # 1. Austin Raynor
    {
        "name": "Austin Raynor",
        "phone": 4348257682,
        "email": None,
        "how_we_met": "Senate work \u2013 Agencies",
        "current_role": "General Counsel at DOGE",
        "domain": "Government/Executive",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/austin-raynor-40514824/",
    },
    # 2. Brenden McCommas
    {
        "name": "Brenden McCommas",
        "phone": "703-505-7476",
        "email": "mccommasbn@state.gov",
        "how_we_met": "Senate work \u2013 Agencies",
        "current_role": "Deputy General Counsel Department of State, State",
        "domain": "Government/Executive",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/brendan-mccommas/",
    },
    # 3. John Ehrett
    {
        "name": "John Ehrett",
        "phone": "972-955-5913",
        "email": None,
        "how_we_met": "Senate work \u2013 Agencies",
        "current_role": "Chief of Staff & Attorney Advisor to Commissioner Mark Meador, FTC",
        "domain": "Government/Executive",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/jsehrett",
    },
    # 4. Thomas Feddo
    {
        "name": "Thomas Feddo",
        "phone": 7039464784,
        "email": "tfeddo@therubiconadvisors.com",
        "how_we_met": "Senate work \u2013 Agencies",
        "current_role": "Former Secretary for Investment Security, CFIUS",
        "domain": "Government/Executive",
        "tier": "New",
        "is_super_connector": False,
        "notes": "Former CFIUS guy -- head who started the regulations",
        "linkedin_url": "https://www.linkedin.com/in/feddo/",
    },
    # 5. Collin Anderson
    {
        "name": "Collin Anderson",
        "phone": None,
        "email": None,
        "how_we_met": "Senate work \u2013 Judiciary",
        "current_role": "Counsel (?), Blumenthal",
        "domain": "Senate/Hill",
        "tier": "New",
        "is_super_connector": False,
        "notes": "had coffee",
        "linkedin_url": None,
    },
    # 6. David Stoopler
    {
        "name": "David Stoopler",
        "phone": None,
        "email": None,
        "how_we_met": "Senate work \u2013 Judiciary",
        "current_role": "Chief Counsel, Blumenthal",
        "domain": "Senate/Hill",
        "tier": "New",
        "is_super_connector": False,
        "notes": "had coffee",
        "linkedin_url": None,
    },
    # 7. Mike Berry
    {
        "name": "Mike Berry",
        "phone": None,
        "email": None,
        "how_we_met": "Senate work \u2013 Judiciary",
        "current_role": "Chief Counsel, Mike Berry",
        "domain": "Senate/Hill",
        "tier": "New",
        "is_super_connector": False,
        "notes": "coffee schedule for Friday 5/2",
        "linkedin_url": None,
        "last_contact_date": "2025-04-30",
    },
    # 8. Ryan Giles
    {
        "name": "Ryan Giles",
        "phone": None,
        "email": None,
        "how_we_met": "Senate work \u2013 Judiciary",
        "current_role": "Chief Counsel for Nominations and Constitution, Grassley",
        "domain": "Senate/Hill",
        "tier": "New",
        "is_super_connector": False,
        "notes": "met on 5/2/2025",
        "linkedin_url": None,
    },
    # 9. Ben Baird
    {
        "name": "Ben Baird",
        "phone": "253-720-1536",
        "email": "baird@meforum.org",
        "how_we_met": "Senate work \u2013 CAIR",
        "current_role": "Director of MEF Action -- political wing, Middle East Forum",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": (
            "Knows a lot about the middle east; some things about CAIR -- for many years, "
            "they have been in immigration. They represented many people involved with terrorism. "
            "They are involved in numerous lawsuits challenging the terrorist watch list. "
            "They have ongoing lawsuits against DHS and subagencies. In 2008, there was a CAIR "
            "maryland and VA chapter (no longer exists). Due to undercover reporting, there was "
            "a manager in the civil rights division named Morris Days, CAIR did some dirt. "
            "They take both federal and state money (Los Angeles money). CAIR has had problems "
            "with numerous federal agencies; there's no reason they should be receiving DHS funding. "
            "Look at some of the no-fly list clients they represented over time. They were involved "
            "in the defense of Samuel Arian, an Islamic Jihad member that is bad. "
            "They are representing American Muslim's for Palestine"
        ),
        "linkedin_url": "https://www.linkedin.com/in/benjamin-baird/",
    },
    # 10. Bhamati Viswanathan
    {
        "name": "Bhamati Viswanathan",
        "phone": "617-981-2707",
        "email": "bhamativiswanathan@yahoo.com",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Professor, New England Law",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": (
            "Professor Viswanathan is likely to be able to testify about the legal aspect "
            "of piracy. She will probably testify that permitting AI companies to train their "
            "models on copyrighted works contradicts the rationale of the Copyright Act and "
            "the fair-use doctrine."
        ),
        "linkedin_url": "https://www.linkedin.com/in/bhamati-viswanathan-b82276105/",
    },
    # 11. Brianna Sacks  (merged Insurance + Journalists contexts)
    {
        "name": "Brianna Sacks",
        "phone": "310-924-5924",
        "email": None,
        "how_we_met": "Senate work \u2013 Journalists / Insurance",
        "current_role": "Reporter, Washington Post Reporter",
        "domain": "Media/Press",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/bmsacks/",
    },
    # 12. Chris Barkley
    {
        "name": "Chris Barkley",
        "phone": "202-697-1005",
        "email": "cbarkley@nmpa.org",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Senior Vice President for Government Affairs, National Music Publishers' Ass'n",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 13. Chris Mellon
    {
        "name": "Chris Mellon",
        "phone": "724-961-9330",
        "email": "christophermellon1@icloud.com",
        "how_we_met": "Senate work \u2013 UFOs",
        "current_role": "Fmr. Undersecretary of Def. for Intelligence",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 14. David Baldacci
    {
        "name": "David Baldacci",
        "phone": "703.946.1326",
        "email": "david@davidbaldacci.com",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Famous Writer",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 15. David Simons
    {
        "name": "David Simons",
        "phone": None,
        "email": "dsimons@bsfllp.com",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Partner, Boies Schiller",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 16. Dillon Guthrie
    {
        "name": "Dillon Guthrie",
        "phone": "202-344-5564",
        "email": "dillon@disclosure.org",
        "how_we_met": "Senate work \u2013 UFOs",
        "current_role": "Disclosure Project/ LLA Piper",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 17. Doug
    {
        "name": "Doug",
        "phone": "732-581-2776",
        "email": None,
        "how_we_met": "Senate work \u2013 Insurance",
        "current_role": "Founder/Helper, APA",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 18. Ed Lee
    {
        "name": "Ed Lee",
        "phone": "415-987-1311",
        "email": "elee9@sce.edu",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Professor, Santa Clara Law School",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": (
            "Agrees with Chhabria. Tends to think pirating is not per se bad, "
            "as long as the ultimate purpose is for a non-infringing use."
        ),
        "linkedin_url": None,
    },
    # 19. Gen. James Clapper
    {
        "name": "Gen. James Clapper",
        "phone": "571-585-1330",
        "email": "jimclapper41@clapperenterprises.net",
        "how_we_met": "Senate work \u2013 UFOs",
        "current_role": None,
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 20. Jesse Panuccio
    {
        "name": "Jesse Panuccio",
        "phone": "617-872-6708",
        "email": "jpanuccio@bsfllp.com",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Partner, Boies Schiller",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/jessepanuccio/",
    },
    # 21. John Cruz
    {
        "name": "John Cruz",
        "phone": "303-570-8925",
        "email": None,
        "how_we_met": "Senate work \u2013 Insurance",
        "current_role": "Insurance Agent, Allstate",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": "Tax fraud; money laundering",
        "linkedin_url": None,
    },
    # 22. John Houghtaling
    {
        "name": "John Houghtaling",
        "phone": "504-400-3899",
        "email": None,
        "how_we_met": "Senate work \u2013 Insurance",
        "current_role": "Helper/Plaintiff's Attorney/Whistleblower, Plaintiff's Attorney",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 23. John Zacharia
    {
        "name": "John Zacharia",
        "phone": "202-845-5091",
        "email": "john@zacharialaw.com",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Former DOJ, Former DOJ/Private Practice Attorney",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": "former DOJ prosecutor of criminal copyright violations",
        "linkedin_url": None,
    },
    # 24. Katherine Chon
    {
        "name": "Katherine Chon",
        "phone": None,
        "email": "katherine.chon@acf.hhs.gov",
        "how_we_met": "Senate work \u2013 Child Sex Trafficking",
        "current_role": "HHS, Office on Trafficking in Persons (OTIP)",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/katherinechon/",
    },
    # 25. Katherine Grayson
    {
        "name": "Katherine Grayson",
        "phone": "415-425-5719",
        "email": "katherine_grayson@motionpictures.org",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Director, Federal Government Affairs, Motion Picture Association",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/katherinegrayson14/",
    },
    # 26. Kevin Malone
    {
        "name": "Kevin Malone",
        "phone": "661-645-1000",
        "email": "kevin.malone@acf.hhs.gov",
        "how_we_met": "Senate work \u2013 Child Sex Trafficking",
        "current_role": "Director, HHS, Office on Trafficking in Persons (OTIP) (Former Dodgers Manager and MLB Player)",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 27. Marla Grossman
    {
        "name": "Marla Grossman",
        "phone": "301-706-7626",
        "email": "grossman@acg-consultants.com",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Partner, ACG Advocacy/Authors Guild and Copyright Alliance",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/marla-grossman-9592415/",
    },
    # 28. Matthew Sag
    {
        "name": "Matthew Sag",
        "phone": "773-255-5856",
        "email": "matthew.james.sag@emory.edu",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Professor of Law, Emory",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": (
            "Professor Sag will act as a foil for the other witnesses. He will testify "
            "that there is no copyright violation when AI companies train on copyrighted works. "
            "Instead, the copyright violation occurs depending on how those AI models output data; "
            "that output may or may not qualify as fair use. Professor Sag has taken some relatively "
            "extreme positions in prior published works, and he will be subject to cross-examination "
            "on these positions."
        ),
        "linkedin_url": "https://www.linkedin.com/in/matthew-sag-05a5606/",
    },
    # 29. Maxwell Pritt
    {
        "name": "Maxwell Pritt",
        "phone": 4157226382,
        "email": "mpritt@bsfllp.com",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Partner, Boies Schiller",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/maxwell-v-pritt-b2477737/",
    },
    # 30. Mike Smith
    {
        "name": "Mike Smith",
        "phone": "412-606-7270",
        "email": "mds@cmu.edu",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Professor of Law, CMU",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": (
            "Professor Smith is an economist who has written about peer-to-peer torrenting "
            "and piracy. He will explain that piracy deleteriously affects innovation. "
            "Clamping down on piracy, in contrast, encourages innovation. He will also explain "
            "the concept of torrenting."
        ),
        "linkedin_url": None,
    },
    # 31. Nicole Brown
    {
        "name": "Nicole Brown",
        "phone": "801-691-6124",
        "email": "nbrown@weissinc.com",
        "how_we_met": "Senate work \u2013 Insurance",
        "current_role": "expert/helper, Weiss",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 32. Ryan Mauro
    {
        "name": "Ryan Mauro",
        "phone": "732-546-5840",
        "email": "yanmauro1986@gmail.com",
        "how_we_met": "Senate work \u2013 Antisemitic Protests",
        "current_role": "Capital Research Center",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": "antisemitic protests",
        "linkedin_url": None,
    },
    # 33. Sam Westrop
    {
        "name": "Sam Westrop",
        "phone": "781-332-2445",
        "email": "westrop@meforum.org",
        "how_we_met": "Senate work \u2013 Antisemitic Protests",
        "current_role": "Middle East Forum",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": "funding expert",
        "linkedin_url": None,
    },
    # 34. Steven Adler
    {
        "name": "Steven Adler",
        "phone": "206-450-3040",
        "email": "steven_adler@alumni.brown.edu",
        "how_we_met": "Senate work \u2013 AI Privacy Hearing",
        "current_role": "Former Head of Safety, OPEN AI",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/sjgadler/",
    },
    # 35. Steven Bush
    {
        "name": "Steven Bush",
        "phone": "817-822-4524",
        "email": None,
        "how_we_met": "Senate work \u2013 Insurance",
        "current_role": "Helper/Attorney, Plaintiff's Attorney Florida",
        "domain": "Policy/Issue-Specific",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/steven-bush-780713103/",
    },
    # 36. Tom Albus
    {
        "name": "Tom Albus",
        "phone": "314-873-8411",
        "email": None,
        "how_we_met": "Senate work \u2013 U.S. Attorney",
        "current_role": "U.S. Attorney, W.D. Missouri",
        "domain": "Law Enforcement",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/tom-albus-0b463813/",
    },
    # 37. Asra Nomani
    {
        "name": "Asra Nomani",
        "phone": "304-685-2189",
        "email": None,
        "how_we_met": "Senate work \u2013 Journalists",
        "current_role": "Reporter, WSJ/Others",
        "domain": "Media/Press",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/asranomani/",
    },
    # 38. Brianna Sacks duplicate -- SKIPPED (merged into #11 above)
    # 39. Brent Johnson
    {
        "name": "Brent Johnson",
        "phone": "415-699-8972",
        "email": "brent@santiagocapital.com",
        "how_we_met": "Senate work \u2013 Private Companies",
        "current_role": "Santiago Capital",
        "domain": "Industry/Policy",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 40. Charlie Albus -- SKIPPED (already exists as social contact)
    # 41. David Simons duplicate -- SKIPPED (already imported as #15)
    # 42. Haywood Talcove
    {
        "name": "Haywood Talcove",
        "phone": "703-980-1957",
        "email": "haywood.talcove@lnssi.com",
        "how_we_met": "Senate work \u2013 Private Companies",
        "current_role": "CEO of LexisNexis Government Risk Solutions",
        "domain": "Industry/Policy",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/haywood-talcove-346b422/",
    },
    # 43. Kyle Bass
    {
        "name": "Kyle Bass",
        "phone": "917-207-5823",
        "email": "k@haymancapital.com",
        "how_we_met": "Senate work \u2013 Private Companies",
        "current_role": "Hayman Capital",
        "domain": "Industry/Policy",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
    # 44. Margaux Poueymirou
    {
        "name": "Margaux Poueymirou",
        "phone": "917-685-9775",
        "email": "mpoueymirou@fsllp.com",
        "how_we_met": "Senate work \u2013 Private Companies",
        "current_role": "Associate, Boies Schiller",
        "domain": "Industry/Policy",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": "https://www.linkedin.com/in/margaux-poueymirou-82b65a255/",
    },
    # 45. Maxwell Pritt duplicate -- SKIPPED (already imported as #29)
    # 46. Nathan Diament
    {
        "name": "Nathan Diament",
        "phone": "202-262-1844",
        "email": "ndiament@ou.org",
        "how_we_met": "Senate work \u2013 Political Donors",
        "current_role": "Union of Orthodox Congregations of America, Executive Director",
        "domain": "Industry/Policy",
        "tier": "New",
        "is_super_connector": False,
        "notes": "Clerked on E.D.N.Y. for Judge Glasser",
        "linkedin_url": "https://www.linkedin.com/in/nathan-diament-31506312/",
    },
    # 47. Slade Bond
    {
        "name": "Slade Bond",
        "phone": None,
        "email": "sbond@cuneolaw.com",
        "how_we_met": "Senate work \u2013 Lobbyist",
        "current_role": "Chair, Public Policy & Legislative Affairs, Cuneo Gilbert & LaDuca, LLP",
        "domain": "Industry/Policy",
        "tier": "New",
        "is_super_connector": False,
        "notes": "Antitrust; knows the book publishers guild",
        "linkedin_url": "https://www.linkedin.com/in/sladebond/",
    },
    # 48. Warren Postman
    {
        "name": "Warren Postman",
        "phone": "617-378-8268",
        "email": "wdp@kellerpostman.com",
        "how_we_met": "Senate work \u2013 Private Companies",
        "current_role": "Named Partner, Keller Postman",
        "domain": "Industry/Policy",
        "tier": "New",
        "is_super_connector": False,
        "notes": None,
        "linkedin_url": None,
    },
]


def ensure_columns(cursor):
    """
    Check if contact_type and professional_tier columns exist.
    If not, add them via ALTER TABLE.
    """
    cursor.execute("PRAGMA table_info(contacts)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    migrations = []
    if "contact_type" not in existing_cols:
        migrations.append(
            "ALTER TABLE contacts ADD COLUMN contact_type TEXT DEFAULT 'social'"
        )
    if "professional_tier" not in existing_cols:
        migrations.append(
            "ALTER TABLE contacts ADD COLUMN professional_tier TEXT"
        )

    for stmt in migrations:
        cursor.execute(stmt)
        col_name = stmt.split("ADD COLUMN ")[1].split(" ")[0]
        print(f"  Added missing column: {col_name}")

    return len(migrations)


def import_professional_contacts():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Start the backend first to create the database, then run this script.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Step 1: Ensure required columns exist
    print("Checking schema...")
    added = ensure_columns(cursor)
    if added:
        conn.commit()
        print(f"  Schema updated ({added} column(s) added).")
    else:
        print("  Schema OK (contact_type and professional_tier columns exist).")

    # Step 2: Get existing contact names to avoid duplicates
    cursor.execute("SELECT name FROM contacts")
    existing_names = {row["name"] for row in cursor.fetchall()}

    now = datetime.utcnow().isoformat()
    imported = 0
    skipped = 0
    skipped_names = []

    for c in PROFESSIONAL_CONTACTS:
        name = c["name"]

        # Duplicate check by name
        if name in existing_names:
            skipped += 1
            skipped_names.append(name)
            continue

        # Format phone
        phone = format_phone(c.get("phone"))

        # Clean other fields
        email = clean_value(c.get("email"))
        notes = clean_value(c.get("notes"))
        linkedin_url = clean_value(c.get("linkedin_url"))
        last_contact_date = c.get("last_contact_date")  # only Mike Berry has this

        cursor.execute(
            """
            INSERT INTO contacts (
                name, phone, email, how_we_met, current_role, domain, tier,
                is_super_connector, notes, linkedin_url,
                contact_type, professional_tier,
                last_contact_date,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                phone,
                email,
                c.get("how_we_met"),
                c.get("current_role"),
                c.get("domain"),
                c.get("tier", "New"),
                c.get("is_super_connector", False),
                notes,
                linkedin_url,
                "professional",           # contact_type
                "Tier 3",                  # professional_tier (default)
                last_contact_date,
                now,
                now,
            ),
        )
        imported += 1
        existing_names.add(name)  # prevent duplicates within this batch

    conn.commit()

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"IMPORT COMPLETE")
    print(f"{'='*60}")
    print(f"  Imported:  {imported} professional contacts")
    print(f"  Skipped:   {skipped} (already in DB)")
    if skipped_names:
        print(f"  Skipped names: {', '.join(skipped_names)}")

    # By domain
    cursor.execute(
        """SELECT domain, COUNT(*) as cnt FROM contacts
           WHERE contact_type = 'professional'
           GROUP BY domain ORDER BY cnt DESC"""
    )
    rows = cursor.fetchall()
    if rows:
        print(f"\nProfessional contacts by domain:")
        for row in rows:
            print(f"  {row['domain']}: {row['cnt']}")

    # By contact_type
    cursor.execute(
        """SELECT contact_type, COUNT(*) as cnt FROM contacts
           GROUP BY contact_type ORDER BY cnt DESC"""
    )
    print(f"\nAll contacts by type:")
    for row in cursor.fetchall():
        print(f"  {row['contact_type'] or 'social'}: {row['cnt']}")

    # Total
    cursor.execute("SELECT COUNT(*) as cnt FROM contacts")
    print(f"\nTotal contacts in DB: {cursor.fetchone()['cnt']}")

    conn.close()


if __name__ == "__main__":
    import_professional_contacts()

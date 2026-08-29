"""Curated default OSINT sources and database seeding.

Sources are stored in osint_sources and fully editable via the API,
so a dead feed can be disabled or replaced from the UI. Seeding is
idempotent — matched by URL, never overwriting user edits.
"""

import json
import uuid

_GN = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _gnews(query: str) -> str:
    from urllib.parse import quote
    return _GN.format(q=quote(query))


# (name, url, category, default_topics)
DEFAULT_SOURCES = [
    # -- China --
    ("SCMP — China", "https://www.scmp.com/rss/4/feed", "news", ["china"]),
    ("The Diplomat", "https://thediplomat.com/feed/", "news", ["china", "taiwan"]),
    ("MERICS", "https://merics.org/en/rss.xml", "think_tank", ["china"]),
    (
        "Google News — China tech policy",
        _gnews('China ("export controls" OR semiconductor OR "artificial intelligence" OR technology policy)'),
        "aggregator",
        ["china"],
    ),
    # -- Taiwan --
    ("Taipei Times", "https://www.taipeitimes.com/xml/index.rss", "news", ["taiwan"]),
    ("Focus Taiwan (CNA)", "https://focustaiwan.tw/rss/politics.xml", "news", ["taiwan"]),
    (
        "Google News — Taiwan security",
        _gnews('Taiwan (strait OR defense OR PLA OR invasion OR semiconductor OR TSMC)'),
        "aggregator",
        ["taiwan"],
    ),
    # -- Semiconductors --
    ("SemiAnalysis", "https://semianalysis.com/feed/", "analysis", ["semiconductors"]),
    ("SemiWiki", "https://semiwiki.com/feed/", "news", ["semiconductors"]),
    ("Tom's Hardware", "https://www.tomshardware.com/feeds/all", "news", ["semiconductors"]),
    (
        "Google News — chip export controls",
        _gnews('(TSMC OR Nvidia OR ASML OR "chip export" OR "semiconductor export" OR "CHIPS Act")'),
        "aggregator",
        ["semiconductors"],
    ),
    # -- AI --
    ("MIT Technology Review", "https://www.technologyreview.com/feed/", "news", ["ai"]),
    ("The Verge — AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "news", ["ai"]),
    ("Import AI (Jack Clark)", "https://jack-clark.net/feed/", "analysis", ["ai"]),
    ("Simon Willison", "https://simonwillison.net/atom/everything/", "analysis", ["ai"]),
    (
        "Google News — AI policy",
        _gnews('"artificial intelligence" (regulation OR policy OR "executive order" OR safety OR export)'),
        "aggregator",
        ["ai"],
    ),
    # -- Cross-cutting think tanks --
    ("CSET Georgetown", "https://cset.georgetown.edu/feed/", "think_tank", ["ai", "china", "semiconductors"]),
]


def seed_default_sources(conn) -> int:
    """Insert any default sources not already present (matched by URL).

    Returns the number of sources inserted. Never modifies existing rows.
    """
    inserted = 0
    for name, url, category, topics in DEFAULT_SOURCES:
        cur = conn.execute(
            """INSERT OR IGNORE INTO osint_sources (id, name, url, category, default_topics)
               VALUES (?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), name, url, category, json.dumps(topics)),
        )
        inserted += cur.rowcount
    conn.commit()
    return inserted

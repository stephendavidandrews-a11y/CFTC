"""OSINT feed fetcher — pulls enabled sources and stores new items.

Network access is confined to this module. Uses conditional GET
(ETag / Last-Modified) to stay polite, and dedupes on (source_id, guid)
via INSERT OR IGNORE so refreshes are idempotent.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

import httpx

from app.osint.parser import parse_feed
from app.osint.topics import tag_text

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 20
MAX_ITEMS_PER_FETCH = 100
USER_AGENT = "CFTC-CommandCenter-OSINT/1.0 (+https://cftc.stephenandrews.org)"


def _make_client() -> httpx.Client:
    return httpx.Client(
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def fetch_source(conn, source: dict, client: httpx.Client) -> dict:
    """Fetch one source and insert new items. Returns a result summary.

    Updates the source row's last_fetched_at / last_status / last_error
    and caching headers regardless of outcome. Commits on success.
    """
    source_id = source["id"]
    result = {"source_id": source_id, "name": source["name"], "new_items": 0, "status": "ok"}

    headers = {}
    if source.get("etag"):
        headers["If-None-Match"] = source["etag"]
    if source.get("last_modified"):
        headers["If-Modified-Since"] = source["last_modified"]

    try:
        resp = client.get(source["url"], headers=headers)
        if resp.status_code == 304:
            result["status"] = "not_modified"
            conn.execute(
                "UPDATE osint_sources SET last_fetched_at = ?, last_status = 'ok', last_error = NULL, updated_at = ? WHERE id = ?",
                (_now(), _now(), source_id),
            )
            conn.commit()
            return result
        resp.raise_for_status()
        items = parse_feed(resp.content)
    except (httpx.HTTPError, ValueError) as e:
        msg = str(e)[:500]
        logger.warning("OSINT fetch failed for %s: %s", source["name"], msg)
        conn.execute(
            "UPDATE osint_sources SET last_fetched_at = ?, last_status = 'error', last_error = ?, updated_at = ? WHERE id = ?",
            (_now(), msg, _now(), source_id),
        )
        conn.commit()
        result["status"] = "error"
        result["error"] = msg
        return result

    try:
        default_topics = json.loads(source.get("default_topics") or "[]")
    except (json.JSONDecodeError, TypeError):
        default_topics = []

    new_items = 0
    for item in items[:MAX_ITEMS_PER_FETCH]:
        topics, relevance = tag_text(item["title"], item["summary"], default_topics)
        cur = conn.execute(
            """INSERT OR IGNORE INTO osint_items
               (id, source_id, guid, title, url, summary, author, published_at, topics, relevance)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                source_id,
                item["guid"],
                item["title"],
                item["url"],
                item["summary"],
                item["author"],
                item["published_at"],
                json.dumps(topics),
                relevance,
            ),
        )
        new_items += cur.rowcount

    conn.execute(
        """UPDATE osint_sources
           SET last_fetched_at = ?, last_status = 'ok', last_error = NULL,
               etag = ?, last_modified = ?, updated_at = ?
           WHERE id = ?""",
        (
            _now(),
            resp.headers.get("etag"),
            resp.headers.get("last-modified"),
            _now(),
            source_id,
        ),
    )
    conn.commit()
    result["new_items"] = new_items
    logger.info("OSINT fetch: %s -> %d new items", source["name"], new_items)
    return result


def refresh_sources(conn, source_id: str | None = None, client: httpx.Client | None = None) -> dict:
    """Fetch all enabled sources (or one specific source).

    Returns {"results": [...], "new_items": total, "errors": n}.
    """
    if source_id:
        rows = conn.execute(
            "SELECT * FROM osint_sources WHERE id = ?", (source_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM osint_sources WHERE enabled = 1"
        ).fetchall()

    own_client = client is None
    if own_client:
        client = _make_client()
    results = []
    try:
        for row in rows:
            results.append(fetch_source(conn, dict(row), client))
    finally:
        if own_client:
            client.close()

    return {
        "results": results,
        "new_items": sum(r["new_items"] for r in results),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "sources_checked": len(results),
    }


def purge_old_items(conn, keep_days: int = 60) -> int:
    """Delete unstarred items older than keep_days (by fetch time)."""
    cur = conn.execute(
        """DELETE FROM osint_items
           WHERE is_starred = 0
           AND julianday(fetched_at) < julianday('now', ?)""",
        (f"-{int(keep_days)} days",),
    )
    conn.commit()
    if cur.rowcount:
        logger.info("OSINT purge: removed %d items older than %d days", cur.rowcount, keep_days)
    return cur.rowcount

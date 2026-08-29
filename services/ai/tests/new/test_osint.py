"""Tests for the OSINT feed module: parser, tagging, fetcher, and API."""

import json

import httpx
import pytest
from app.osint.fetcher import fetch_source, purge_old_items, refresh_sources
from app.osint.parser import parse_feed, parse_feed_date
from app.osint.sources import DEFAULT_SOURCES, seed_default_sources
from app.osint.topics import TOPICS, tag_text

RSS_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>TSMC expands Arizona fab amid export controls</title>
      <link>https://example.com/tsmc-arizona</link>
      <guid>tsmc-arizona-1</guid>
      <description><![CDATA[<p>TSMC said the <b>semiconductor</b> plant will&hellip;</p>]]></description>
      <pubDate>Fri, 28 Aug 2026 10:30:00 GMT</pubDate>
      <dc:creator>Jane Reporter</dc:creator>
    </item>
    <item>
      <title>Beijing responds to Taiwan strait transit</title>
      <link>https://example.com/strait</link>
      <pubDate>Thu, 27 Aug 2026 08:00:00 +0800</pubDate>
    </item>
    <item>
      <title></title>
      <link>https://example.com/no-title</link>
    </item>
  </channel>
</rss>"""

ATOM_SAMPLE = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Test</title>
  <entry>
    <title>New frontier model released by OpenAI</title>
    <link rel="alternate" href="https://example.com/model"/>
    <id>urn:uuid:model-1</id>
    <summary>A large language model with improved reasoning.</summary>
    <published>2026-08-28T12:00:00Z</published>
    <author><name>Alice</name></author>
  </entry>
</feed>"""


# ── Parser ──────────────────────────────────────────────────────────────────


def test_parse_rss():
    items = parse_feed(RSS_SAMPLE)
    assert len(items) == 2  # titleless item dropped
    first = items[0]
    assert first["guid"] == "tsmc-arizona-1"
    assert first["title"] == "TSMC expands Arizona fab amid export controls"
    assert first["url"] == "https://example.com/tsmc-arizona"
    assert "semiconductor plant" in first["summary"]
    assert "<" not in first["summary"]
    assert first["author"] == "Jane Reporter"
    assert first["published_at"] == "2026-08-28T10:30:00"
    # Item without guid falls back to link; TZ offset normalized to UTC
    assert items[1]["guid"] == "https://example.com/strait"
    assert items[1]["published_at"] == "2026-08-27T00:00:00"


def test_parse_atom():
    items = parse_feed(ATOM_SAMPLE)
    assert len(items) == 1
    item = items[0]
    assert item["guid"] == "urn:uuid:model-1"
    assert item["url"] == "https://example.com/model"
    assert item["author"] == "Alice"
    assert item["published_at"] == "2026-08-28T12:00:00"


def test_parse_invalid_feed():
    with pytest.raises(ValueError):
        parse_feed(b"<html><body>Not a feed</body></html>")
    with pytest.raises(ValueError):
        parse_feed(b"complete garbage {{{")


def test_parse_feed_date_formats():
    assert parse_feed_date("Fri, 28 Aug 2026 10:30:00 GMT") == "2026-08-28T10:30:00"
    assert parse_feed_date("2026-08-28T12:00:00Z") == "2026-08-28T12:00:00"
    assert parse_feed_date("2026-08-28T08:00:00-04:00") == "2026-08-28T12:00:00"
    assert parse_feed_date("not a date") is None
    assert parse_feed_date("") is None


# ── Topic tagging ───────────────────────────────────────────────────────────


def test_tag_text_topics():
    topics, relevance = tag_text(
        "TSMC warns on Taiwan strait risk", "Chip exports to China face new controls."
    )
    assert set(topics) == {"taiwan", "semiconductors", "china"}
    assert relevance > 0


def test_tag_text_ai_case_sensitivity():
    topics, _ = tag_text("New AI executive order signed")
    assert "ai" in topics
    # Lowercase "ai" inside words must not match
    topics, _ = tag_text("Air quality in Bahrain said to fail")
    assert "ai" not in topics


def test_tag_text_default_topics():
    topics, relevance = tag_text("Weekly newsletter", "", default_topics=["china"])
    assert topics == ["china"]
    assert relevance == 1
    # Unknown default topics ignored
    topics, _ = tag_text("Weekly newsletter", "", default_topics=["bogus"])
    assert topics == []


# ── Seeding ─────────────────────────────────────────────────────────────────


def test_seed_default_sources_idempotent(db):
    inserted = seed_default_sources(db)
    assert inserted == len(DEFAULT_SOURCES)
    assert seed_default_sources(db) == 0  # second run inserts nothing
    count = db.execute("SELECT COUNT(*) FROM osint_sources").fetchone()[0]
    assert count == len(DEFAULT_SOURCES)


# ── Fetcher ─────────────────────────────────────────────────────────────────


def _add_source(db, url="https://example.com/feed.xml", name="Test Source", topics=None):
    import uuid

    source_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO osint_sources (id, name, url, category, default_topics) VALUES (?, ?, ?, 'news', ?)",
        (source_id, name, url, json.dumps(topics or [])),
    )
    db.commit()
    return source_id


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_source_inserts_and_dedupes(db):
    source_id = _add_source(db)

    def handler(request):
        return httpx.Response(200, content=RSS_SAMPLE, headers={"ETag": '"abc"'})

    with _mock_client(handler) as client:
        source = dict(db.execute("SELECT * FROM osint_sources WHERE id = ?", (source_id,)).fetchone())
        result = fetch_source(db, source, client)
        assert result["status"] == "ok"
        assert result["new_items"] == 2

        # Second fetch of same content inserts nothing new
        source = dict(db.execute("SELECT * FROM osint_sources WHERE id = ?", (source_id,)).fetchone())
        assert source["etag"] == '"abc"'
        result = fetch_source(db, source, client)
        assert result["new_items"] == 0

    row = db.execute(
        "SELECT * FROM osint_items WHERE guid = 'tsmc-arizona-1'"
    ).fetchone()
    topics = json.loads(row["topics"])
    assert "semiconductors" in topics
    assert row["relevance"] > 0


def test_fetch_source_not_modified(db):
    source_id = _add_source(db)
    db.execute("UPDATE osint_sources SET etag = '\"abc\"' WHERE id = ?", (source_id,))
    db.commit()

    def handler(request):
        assert request.headers.get("If-None-Match") == '"abc"'
        return httpx.Response(304)

    with _mock_client(handler) as client:
        source = dict(db.execute("SELECT * FROM osint_sources WHERE id = ?", (source_id,)).fetchone())
        result = fetch_source(db, source, client)
    assert result["status"] == "not_modified"
    assert result["new_items"] == 0


def test_fetch_source_error_recorded(db):
    source_id = _add_source(db)

    def handler(request):
        return httpx.Response(503)

    with _mock_client(handler) as client:
        source = dict(db.execute("SELECT * FROM osint_sources WHERE id = ?", (source_id,)).fetchone())
        result = fetch_source(db, source, client)
    assert result["status"] == "error"
    row = db.execute("SELECT last_status, last_error FROM osint_sources WHERE id = ?", (source_id,)).fetchone()
    assert row["last_status"] == "error"
    assert row["last_error"]


def test_refresh_sources_skips_disabled(db):
    enabled_id = _add_source(db, url="https://example.com/a.xml", name="A")
    disabled_id = _add_source(db, url="https://example.com/b.xml", name="B")
    db.execute("UPDATE osint_sources SET enabled = 0 WHERE id = ?", (disabled_id,))
    db.commit()

    def handler(request):
        return httpx.Response(200, content=ATOM_SAMPLE)

    with _mock_client(handler) as client:
        summary = refresh_sources(db, client=client)
    assert summary["sources_checked"] == 1
    assert summary["results"][0]["source_id"] == enabled_id


def test_purge_old_items_keeps_starred(db):
    source_id = _add_source(db)
    db.execute(
        "INSERT INTO osint_items (id, source_id, guid, title, fetched_at, is_starred) "
        "VALUES ('old1', ?, 'g1', 'Old item', datetime('now', '-90 days'), 0)",
        (source_id,),
    )
    db.execute(
        "INSERT INTO osint_items (id, source_id, guid, title, fetched_at, is_starred) "
        "VALUES ('old2', ?, 'g2', 'Old starred', datetime('now', '-90 days'), 1)",
        (source_id,),
    )
    db.execute(
        "INSERT INTO osint_items (id, source_id, guid, title) VALUES ('new1', ?, 'g3', 'Fresh')",
        (source_id,),
    )
    db.commit()
    assert purge_old_items(db, keep_days=60) == 1
    remaining = {r[0] for r in db.execute("SELECT id FROM osint_items").fetchall()}
    assert remaining == {"old2", "new1"}


# ── API ─────────────────────────────────────────────────────────────────────


def _insert_item(db, source_id, guid, title, topics, published_at="2026-08-28T10:00:00", **kw):
    import uuid

    item_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO osint_items (id, source_id, guid, title, url, summary, published_at, topics, relevance, is_read, is_starred) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            item_id, source_id, guid, title,
            kw.get("url", "https://example.com/x"),
            kw.get("summary", ""),
            published_at,
            json.dumps(topics),
            kw.get("relevance", 1),
            kw.get("is_read", 0),
            kw.get("is_starred", 0),
        ),
    )
    db.commit()
    return item_id


def test_api_list_items_filters(db, client):
    source_id = _add_source(db)
    _insert_item(db, source_id, "g1", "Chip news", ["semiconductors"], "2026-08-28T10:00:00")
    _insert_item(db, source_id, "g2", "Taiwan election", ["taiwan"], "2026-08-28T11:00:00")
    _insert_item(db, source_id, "g3", "AI act passes", ["ai"], "2026-08-28T12:00:00", is_read=1)

    r = client.get("/ai/api/osint/items")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["items"][0]["title"] == "AI act passes"  # newest first
    assert body["items"][0]["source_name"] == "Test Source"

    r = client.get("/ai/api/osint/items?topic=taiwan")
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["title"] == "Taiwan election"

    r = client.get("/ai/api/osint/items?unread_only=true")
    assert r.json()["total"] == 2

    r = client.get("/ai/api/osint/items?q=chip")
    assert r.json()["total"] == 1

    r = client.get("/ai/api/osint/items?topic=bogus")
    assert r.status_code == 422


def test_api_topics_counts(db, client):
    source_id = _add_source(db)
    _insert_item(db, source_id, "g1", "Chip news", ["semiconductors", "china"])
    _insert_item(db, source_id, "g2", "More chips", ["semiconductors"], is_read=1)

    r = client.get("/ai/api/osint/topics")
    assert r.status_code == 200
    body = r.json()
    assert body["all"]["total"] == 2
    assert body["all"]["unread"] == 1
    by_slug = {t["slug"]: t for t in body["topics"]}
    assert set(by_slug) == set(TOPICS)
    assert by_slug["semiconductors"]["total"] == 2
    assert by_slug["china"]["total"] == 1


def test_api_read_star_mark_all(db, client):
    source_id = _add_source(db)
    item_id = _insert_item(db, source_id, "g1", "Chip news", ["semiconductors"])
    _insert_item(db, source_id, "g2", "Taiwan news", ["taiwan"])

    r = client.post(f"/ai/api/osint/items/{item_id}/read", json={"is_read": True})
    assert r.status_code == 200
    assert db.execute("SELECT is_read FROM osint_items WHERE id = ?", (item_id,)).fetchone()[0] == 1

    r = client.post(f"/ai/api/osint/items/{item_id}/star", json={"is_starred": True})
    assert r.status_code == 200
    assert db.execute("SELECT is_starred FROM osint_items WHERE id = ?", (item_id,)).fetchone()[0] == 1

    r = client.post("/ai/api/osint/items/missing/read", json={"is_read": True})
    assert r.status_code == 404

    r = client.post("/ai/api/osint/items/mark-all-read?topic=taiwan")
    assert r.status_code == 200
    assert r.json()["marked_read"] == 1
    unread = db.execute("SELECT COUNT(*) FROM osint_items WHERE is_read = 0").fetchone()[0]
    assert unread == 0


def test_api_source_crud(db, client):
    r = client.post(
        "/ai/api/osint/sources",
        json={"name": "My Feed", "url": "https://example.com/f.xml", "default_topics": ["china"]},
    )
    assert r.status_code == 201
    source = r.json()
    assert source["default_topics"] == ["china"]

    # Duplicate URL rejected
    r = client.post("/ai/api/osint/sources", json={"name": "Dup", "url": "https://example.com/f.xml"})
    assert r.status_code == 409

    # Invalid topic rejected
    r = client.post(
        "/ai/api/osint/sources",
        json={"name": "Bad", "url": "https://example.com/g.xml", "default_topics": ["bogus"]},
    )
    assert r.status_code == 422

    # Non-http URL rejected
    r = client.post("/ai/api/osint/sources", json={"name": "Bad", "url": "ftp://example.com/g"})
    assert r.status_code == 422

    r = client.patch(f"/ai/api/osint/sources/{source['id']}", json={"enabled": False, "name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["enabled"] == 0
    assert r.json()["name"] == "Renamed"

    r = client.get("/ai/api/osint/sources")
    assert r.status_code == 200
    assert r.json()["count"] >= 1
    assert "item_count" in r.json()["sources"][0]

    r = client.delete(f"/ai/api/osint/sources/{source['id']}")
    assert r.status_code == 204
    r = client.delete(f"/ai/api/osint/sources/{source['id']}")
    assert r.status_code == 404


def test_api_seed_defaults(db, client):
    r = client.post("/ai/api/osint/sources/seed-defaults")
    assert r.status_code == 200
    assert r.json()["inserted"] == len(DEFAULT_SOURCES)
    r = client.post("/ai/api/osint/sources/seed-defaults")
    assert r.json()["inserted"] == 0


def test_api_refresh_unknown_source(db, client):
    r = client.post("/ai/api/osint/refresh?source_id=missing")
    assert r.status_code == 404

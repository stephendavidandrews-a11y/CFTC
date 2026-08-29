"""RSS 2.0 / Atom feed parser for OSINT sources.

Uses lxml with recovery mode so slightly malformed real-world feeds
still parse. Returns plain dicts; no database access here.
"""

import html
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from lxml import etree

logger = logging.getLogger(__name__)

MAX_SUMMARY_CHARS = 600

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    """Strip tags and collapse whitespace from a feed summary/description."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    if len(text) > MAX_SUMMARY_CHARS:
        text = text[: MAX_SUMMARY_CHARS - 1].rsplit(" ", 1)[0] + "…"
    return text


def _localname(el) -> str:
    """Tag name without namespace."""
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def _child_text(el, name: str) -> str:
    """Text of the first direct child with the given local name."""
    for child in el:
        if _localname(child) == name:
            return "".join(child.itertext()).strip()
    return ""


def parse_feed_date(raw: str) -> str | None:
    """Normalize an RFC 822 or ISO 8601 feed date to UTC ISO format."""
    if not raw:
        return None
    raw = raw.strip()
    dt = None
    try:
        dt = parsedate_to_datetime(raw)
    except (ValueError, TypeError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat(timespec="seconds")


def _parse_rss_item(item) -> dict:
    link = _child_text(item, "link")
    guid = _child_text(item, "guid") or link
    summary = _child_text(item, "description") or _child_text(item, "encoded")
    return {
        "guid": guid,
        "title": _strip_html(_child_text(item, "title")),
        "url": link or None,
        "summary": _strip_html(summary),
        "author": _child_text(item, "creator") or _child_text(item, "author") or None,
        "published_at": parse_feed_date(_child_text(item, "pubDate") or _child_text(item, "date")),
    }


def _parse_atom_entry(entry) -> dict:
    link = None
    for child in entry:
        if _localname(child) == "link":
            rel = child.get("rel", "alternate")
            if rel == "alternate" or link is None:
                link = child.get("href")
    author = None
    for child in entry:
        if _localname(child) == "author":
            author = _child_text(child, "name") or None
            break
    summary = _child_text(entry, "summary") or _child_text(entry, "content")
    published = _child_text(entry, "published") or _child_text(entry, "updated")
    return {
        "guid": _child_text(entry, "id") or link,
        "title": _strip_html(_child_text(entry, "title")),
        "url": link,
        "summary": _strip_html(summary),
        "author": author,
        "published_at": parse_feed_date(published),
    }


def parse_feed(content: bytes) -> list[dict]:
    """Parse RSS 2.0 or Atom feed bytes into a list of item dicts.

    Each dict has: guid, title, url, summary, author, published_at.
    Items without a guid/link or title are dropped. Raises ValueError
    when the payload is not a recognizable feed.
    """
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True)
    try:
        root = etree.fromstring(content, parser=parser)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Feed is not valid XML: {e}") from e
    if root is None:
        raise ValueError("Feed is not valid XML (empty document)")

    root_name = _localname(root)
    items: list[dict] = []

    if root_name in ("rss", "RDF"):
        raw_items = root.iter()
        items = [_parse_rss_item(el) for el in raw_items if _localname(el) == "item"]
    elif root_name == "feed":
        items = [_parse_atom_entry(el) for el in root if _localname(el) == "entry"]
    else:
        raise ValueError(f"Unrecognized feed root element: <{root_name or root.tag}>")

    return [i for i in items if i["guid"] and i["title"]]

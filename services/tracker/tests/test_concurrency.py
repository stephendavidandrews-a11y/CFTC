"""Tests for concurrency module — ETag generation and If-Match checking."""

import pytest
from unittest.mock import MagicMock
from app.concurrency import get_etag, check_etag
from fastapi import HTTPException
from tests.conftest import seed_meeting


# ── get_etag ──────────────────────────────────────────────────────────────────


def test_get_etag_format():
    """get_etag wraps updated_at in double quotes."""
    record = {"updated_at": "2026-03-20T10:00:00"}
    assert get_etag(record) == '"2026-03-20T10:00:00"'


def test_get_etag_different_timestamps():
    """Different updated_at values produce different ETags."""
    r1 = {"updated_at": "2026-03-20T10:00:00"}
    r2 = {"updated_at": "2026-03-20T11:00:00"}
    assert get_etag(r1) != get_etag(r2)


# ── check_etag ────────────────────────────────────────────────────────────────


def _mock_request(if_match=None):
    """Create a mock Request with optional If-Match header."""
    req = MagicMock()
    req.headers = {}
    if if_match is not None:
        req.headers["if-match"] = if_match
    return req


def test_check_etag_no_header_passes():
    """check_etag is a no-op when If-Match header is absent."""
    record = {"updated_at": "2026-03-20T10:00:00"}
    # Should not raise
    check_etag(_mock_request(), record)


def test_check_etag_matching_passes():
    """check_etag passes when If-Match matches current record."""
    record = {"updated_at": "2026-03-20T10:00:00"}
    check_etag(_mock_request('"2026-03-20T10:00:00"'), record)


def test_check_etag_mismatch_raises_409():
    """check_etag raises 409 when If-Match does not match."""
    record = {"updated_at": "2026-03-20T10:00:00"}
    with pytest.raises(HTTPException) as exc_info:
        check_etag(_mock_request('"2026-03-20T09:00:00"'), record)
    assert exc_info.value.status_code == 409


def test_check_etag_strips_weak_prefix():
    """check_etag handles W/ prefix (added by nginx gzip)."""
    record = {"updated_at": "2026-03-20T10:00:00"}
    # W/ prefix should be stripped, then match
    check_etag(_mock_request('W/"2026-03-20T10:00:00"'), record)


# ── Integration: ETag round-trip via meeting endpoint ─────────────────────────


def test_etag_round_trip_meeting(client, auth_headers, db):
    """GET meeting returns ETag; PUT with that ETag succeeds."""
    m = seed_meeting(db, title="Concurrency Test")
    get_resp = client.get(f"/tracker/meetings/{m['id']}", headers=auth_headers)
    assert get_resp.status_code == 200
    etag = get_resp.headers["etag"]

    put_resp = client.put(
        f"/tracker/meetings/{m['id']}",
        json={"title": "Updated"},
        headers={**auth_headers, "If-Match": etag},
    )
    assert put_resp.status_code == 200


def test_etag_stale_conflict(client, auth_headers, db):
    """PUT with a stale ETag returns 409."""
    m = seed_meeting(db, title="Stale Test")
    stale_etag = '"1999-01-01T00:00:00"'
    resp = client.put(
        f"/tracker/meetings/{m['id']}",
        json={"title": "Should Fail"},
        headers={**auth_headers, "If-Match": stale_etag},
    )
    assert resp.status_code == 409

"""Hunter client: retries, rate limiting, caching, and key redaction.

No test here makes a real Hunter call. Every response is mocked.
"""

import asyncio
import sqlite3
import time

import httpx
import pytest
from app.enrichment import hunter_client as hc
from app.enrichment.hunter_client import (
    HunterAuthError,
    HunterClient,
    HunterRateLimiter,
    cache_get,
    cache_put,
)
from app.schema import init_schema


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    yield conn
    conn.close()


def _client_with(handler, **policy_overrides):
    """Build a HunterClient whose transport is a MockTransport."""
    policy = {
        "enrichment_policy": {
            "requests_per_second": 1000,  # do not slow the tests down
            "cache_ttl_days": 90,
            **policy_overrides,
        }
    }
    client = HunterClient(api_key="test-key-abc123", policy=policy)
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), trust_env=False
    )
    return client


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Email Finder
# ---------------------------------------------------------------------------

FINDER_FOUND = {
    "data": {
        "email": "jane.doe@example.gov",
        "score": 94,
        "position": "Senior Counsel",
        "linkedin_url": "https://www.linkedin.com/in/janedoe",
        "twitter": None,
        "verification": {"status": "deliverable"},
        "sources": [{"uri": "a"}, {"uri": "b"}],
    }
}


def test_find_email_parses_a_hit(db):
    def handler(request):
        assert "api_key=test-key-abc123" in str(request.url)
        return httpx.Response(200, json=FINDER_FOUND)

    async def go():
        async with _client_with(handler) as c:
            return await c.find_email(db, "Jane", "Doe", "example.gov")

    r = _run(go())
    assert r.status == "found"
    assert r.email == "jane.doe@example.gov"
    assert r.score == 94
    assert r.verification == "deliverable"
    assert r.position == "Senior Counsel"
    assert r.linkedin_url == "https://www.linkedin.com/in/janedoe"
    assert r.sources_count == 2
    assert r.credits_used == 1
    assert r.from_cache is False


def test_null_email_is_not_found_not_an_error(db):
    def handler(request):
        return httpx.Response(200, json={"data": {"email": None}})

    async def go():
        async with _client_with(handler) as c:
            return await c.find_email(db, "Nobody", "Here", "example.gov")

    r = _run(go())
    assert r.status == "not_found"
    assert r.email is None
    assert r.credits_used == 1


def test_404_is_a_real_answer_and_gets_cached(db):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404, json={"errors": [{"details": "no results"}]})

    async def go():
        async with _client_with(handler) as c:
            first = await c.find_email(db, "Ghost", "Person", "example.gov")
            second = await c.find_email(db, "Ghost", "Person", "example.gov")
            return first, second

    first, second = _run(go())
    assert first.status == "not_found"
    assert first.credits_used == 1
    # The second lookup is served from cache — no second HTTP call, no credit.
    assert second.status == "not_found"
    assert second.from_cache is True
    assert second.credits_used == 0
    assert len(calls) == 1


def test_cache_hit_costs_no_credit_and_makes_no_call(db):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=FINDER_FOUND)

    async def go():
        async with _client_with(handler) as c:
            a = await c.find_email(db, "Jane", "Doe", "example.gov")
            b = await c.find_email(db, "jane", "DOE", "Example.gov")  # case-insensitive
            return a, b

    a, b = _run(go())
    assert len(calls) == 1, "second lookup should not hit the network"
    assert a.credits_used == 1
    assert b.credits_used == 0
    assert b.from_cache is True
    assert b.email == a.email


# ---------------------------------------------------------------------------
# Retries
# ---------------------------------------------------------------------------


def test_429_retries_then_succeeds(db, monkeypatch):
    monkeypatch.setattr(hc, "BACKOFF_SECONDS", [0.0, 0.0, 0.0])
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={})
        return httpx.Response(200, json=FINDER_FOUND)

    async def go():
        async with _client_with(handler) as c:
            return await c.find_email(db, "Jane", "Doe", "example.gov")

    r = _run(go())
    assert r.status == "found"
    assert len(calls) == 3


def test_429_gives_up_after_max_attempts(db, monkeypatch):
    monkeypatch.setattr(hc, "BACKOFF_SECONDS", [0.0, 0.0, 0.0])
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "0"}, json={})

    async def go():
        async with _client_with(handler) as c:
            return await c.find_email(db, "Jane", "Doe", "example.gov")

    r = _run(go())
    # Terminal after retries: recorded as an error row, job continues.
    assert r.status == "error"
    assert len(calls) == hc.MAX_ATTEMPTS


def test_5xx_retries(db, monkeypatch):
    monkeypatch.setattr(hc, "BACKOFF_SECONDS", [0.0, 0.0, 0.0])
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 2:
            return httpx.Response(503, json={})
        return httpx.Response(200, json=FINDER_FOUND)

    async def go():
        async with _client_with(handler) as c:
            return await c.find_email(db, "Jane", "Doe", "example.gov")

    assert _run(go()).status == "found"
    assert len(calls) == 2


def test_400_is_terminal_and_does_not_retry(db):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, json={"errors": [{"details": "bad domain"}]})

    async def go():
        async with _client_with(handler) as c:
            return await c.find_email(db, "Jane", "Doe", "not a domain")

    r = _run(go())
    assert r.status == "error"
    assert "bad domain" in r.error_detail
    assert len(calls) == 1, "4xx must not be retried"


def test_401_raises_auth_error_to_fail_the_whole_job(db):
    def handler(request):
        return httpx.Response(401, json={"errors": [{"details": "invalid api key"}]})

    async def go():
        async with _client_with(handler) as c:
            return await c.find_email(db, "Jane", "Doe", "example.gov")

    with pytest.raises(HunterAuthError):
        _run(go())


def test_missing_key_raises_before_any_request():
    def handler(request):  # pragma: no cover - must never be reached
        raise AssertionError("should not make a request without a key")

    client = HunterClient(api_key="", policy={"enrichment_policy": {}})
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), trust_env=False
    )

    async def go():
        return await client.account()

    with pytest.raises(HunterAuthError):
        _run(go())


# ---------------------------------------------------------------------------
# Key redaction
# ---------------------------------------------------------------------------


def test_api_key_never_appears_in_error_message(db, monkeypatch):
    """A Hunter error that echoes the key back must not carry it into our logs."""
    monkeypatch.setattr(hc, "HUNTER_API_KEY", "supersecret")

    def handler(request):
        return httpx.Response(
            400, json={"errors": [{"details": "bad key supersecret in request"}]}
        )

    async def go():
        client = HunterClient(api_key="supersecret", policy={"enrichment_policy": {}})
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), trust_env=False
        )
        try:
            return await client.find_email(db, "A", "B", "example.gov")
        finally:
            await client._client.aclose()

    r = _run(go())
    assert r.status == "error"
    assert "supersecret" not in r.error_detail
    assert "***" in r.error_detail


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


def test_rate_limiter_paces_calls():
    limiter = HunterRateLimiter(rate_per_second=20)  # 50ms apart

    async def go():
        start = time.monotonic()
        for _ in range(4):
            await limiter.acquire()
        return time.monotonic() - start

    elapsed = _run(go())
    # 4 acquisitions at 20/s means at least 3 gaps of 50ms.
    assert elapsed >= 0.10, f"limiter did not pace calls (elapsed {elapsed:.3f}s)"


def test_rate_limiter_rejects_zero_rate():
    assert HunterRateLimiter(0).rate > 0


# ---------------------------------------------------------------------------
# Combined enrichment
# ---------------------------------------------------------------------------


def test_enrich_person_extracts_linkedin_and_title(db):
    body = {
        "data": {
            "person": {
                "employment": {
                    "title": "Deputy Director",
                    "seniority": "executive",
                    "role": "legal",
                },
                "linkedin": {"handle": "in/janedoe"},
                "twitter": {"handle": "jdoe"},
            }
        }
    }

    def handler(request):
        return httpx.Response(200, json=body)

    async def go():
        async with _client_with(handler) as c:
            return await c.enrich_person(db, "jane.doe@example.gov")

    r = _run(go())
    assert r.status == "found"
    assert r.position == "Deputy Director"
    assert r.seniority == "executive"
    assert r.department == "legal"
    assert r.linkedin_url == "https://www.linkedin.com/in/janedoe"
    assert r.twitter == "jdoe"
    assert r.credits_used == 1


def test_enrich_person_empty_person_is_not_found(db):
    def handler(request):
        return httpx.Response(200, json={"data": {}})

    async def go():
        async with _client_with(handler) as c:
            return await c.enrich_person(db, "nobody@example.gov")

    assert _run(go()).status == "not_found"


# ---------------------------------------------------------------------------
# Free endpoints
# ---------------------------------------------------------------------------


def test_account_returns_credit_data(db):
    def handler(request):
        return httpx.Response(
            200, json={"data": {"requests": {"searches": {"available": 500, "used": 12}}}}
        )

    async def go():
        async with _client_with(handler) as c:
            return await c.account()

    data = _run(go())
    assert data["requests"]["searches"]["available"] == 500


def test_email_count_is_free_and_parsed(db):
    def handler(request):
        return httpx.Response(200, json={"data": {"total": 42, "personal_emails": 40}})

    async def go():
        async with _client_with(handler) as c:
            return await c.email_count("example.gov")

    assert _run(go())["total"] == 42


# ---------------------------------------------------------------------------
# Cache primitives
# ---------------------------------------------------------------------------


def test_expired_cache_entry_misses(db):
    cache_put(db, "k1", "email_finder", {"data": {"email": "x@y.z"}}, ttl_days=30)
    db.execute(
        "UPDATE enrichment_cache SET expires_at = ? WHERE lookup_key = 'k1'",
        ("2020-01-01T00:00:00",),
    )
    assert cache_get(db, "k1") is None


def test_zero_ttl_means_never_expires(db):
    cache_put(db, "k1b", "email_finder", {"v": 1}, ttl_days=0)
    row = db.execute(
        "SELECT expires_at FROM enrichment_cache WHERE lookup_key = 'k1b'"
    ).fetchone()
    assert row["expires_at"] is None
    assert cache_get(db, "k1b") == {"v": 1}


def test_cache_put_is_an_upsert(db):
    cache_put(db, "k2", "email_finder", {"v": 1}, ttl_days=30)
    cache_put(db, "k2", "email_finder", {"v": 2}, ttl_days=30)
    assert cache_get(db, "k2") == {"v": 2}
    rows = db.execute(
        "SELECT COUNT(*) c FROM enrichment_cache WHERE lookup_key = 'k2'"
    ).fetchone()["c"]
    assert rows == 1


def test_cache_records_hit_count(db):
    cache_put(db, "k3", "email_finder", {"v": 1}, ttl_days=30)
    cache_get(db, "k3")
    cache_get(db, "k3")
    hits = db.execute(
        "SELECT hit_count FROM enrichment_cache WHERE lookup_key = 'k3'"
    ).fetchone()["hit_count"]
    assert hits == 2


def test_corrupt_cache_row_misses_instead_of_raising(db):
    db.execute(
        "INSERT INTO enrichment_cache (id, lookup_key, endpoint, response_json) "
        "VALUES ('x', 'k4', 'email_finder', 'not json')"
    )
    assert cache_get(db, "k4") is None

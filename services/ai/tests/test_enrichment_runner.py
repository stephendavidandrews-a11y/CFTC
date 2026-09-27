"""Runner, committer, and export — end to end against a real sqlite DB.

Hunter and the tracker are both mocked. Nothing here makes a network call.
"""

import asyncio
import json
import sqlite3

import httpx
import pytest
from app.enrichment import committer, export, runner
from app.enrichment.hunter_client import HunterClient
from app.enrichment.parsing import SOURCE_SPREADSHEET
from app.schema import init_schema

POLICY = {
    "enrichment_policy": {
        "auto_accept_score": 90,
        "reject_below_score": 50,
        "allow_risky_emails": False,
        "max_concurrency": 3,
        "requests_per_second": 1000,
        "cache_ttl_days": 90,
        "fuzzy_name_threshold": 0.85,
        "require_egress_acknowledgement": True,
        "propose_org_domain_writeback": True,
    }
}

TRACKER_CONTEXT = {
    "people": [
        {
            "id": "p1",
            "full_name": "Existing Person",
            "email": "existing@cftc.gov",
            "organization_id": "o1",
            "email_verification_status": "deliverable",
            "title": "Counsel",
            "linkedin_url": None,
        }
    ],
    "organizations": [
        {"id": "o1", "name": "Commodity Futures Trading Commission",
         "short_name": "CFTC", "primary_domain": "cftc.gov"},
        {"id": "o2", "name": "Acme Corporation", "short_name": "Acme",
         "primary_domain": None},
    ],
}


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _no_tracker_calls(monkeypatch):
    """Every test gets the canned tracker context unless it overrides."""
    async def fake_context():
        return TRACKER_CONTEXT

    monkeypatch.setattr(runner, "fetch_tracker_context", fake_context)


def _mock_hunter(handler, policy=None):
    client = HunterClient(api_key="k", policy=policy or POLICY)
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), trust_env=False
    )
    return client


def _finder(email, score=95, verification="deliverable"):
    return {
        "data": {
            "email": email,
            "score": score,
            "verification": {"status": verification},
            "position": "Analyst",
            "sources": [],
        }
    }


def _seed_job(db, rows, mapping, enrich_profile=False, ack=True, cap=None):
    job_id = runner.create_job(
        db,
        filename="contacts.csv",
        stored_path="/tmp/contacts.csv",
        file_sha256="abc",
        source_type=SOURCE_SPREADSHEET,
        enrich_profile=enrich_profile,
    )
    runner.store_rows(db, job_id, rows)
    runner.set_mapping(db, job_id, mapping)
    if ack:
        runner.acknowledge_egress(db, job_id, cap)
    return job_id


MAPPING = {"First Name": "first_name", "Last Name": "last_name", "Company": "org_name"}


# ---------------------------------------------------------------------------
# Job creation and resolution
# ---------------------------------------------------------------------------


def test_store_rows_preserves_raw_and_order(db):
    rows = [
        {"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"},
        {"First Name": "John", "Last Name": "Roe", "Company": "Acme"},
    ]
    job_id = _seed_job(db, rows, MAPPING)
    stored = db.execute(
        "SELECT row_number, raw_row FROM enrichment_rows WHERE job_id = ? ORDER BY row_number",
        (job_id,),
    ).fetchall()
    assert [r["row_number"] for r in stored] == [1, 2]
    assert json.loads(stored[0]["raw_row"])["First Name"] == "Jane"


def test_resolve_marks_rows_needing_lookup(db):
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING)
    summary = asyncio.run(runner.resolve_rows(db, job_id, POLICY))
    assert summary["total"] == 1
    assert summary["to_lookup"] == 1
    assert summary["credits_estimated"] == 1
    row = db.execute(
        "SELECT * FROM enrichment_rows WHERE job_id = ?", (job_id,)
    ).fetchone()
    assert row["domain"] == "cftc.gov", "domain comes from the resolved org"
    assert row["resolved_organization_id"] == "o1"
    assert row["hunter_status"] == "pending"


def test_resolve_skips_a_row_with_no_domain(db):
    """Acme has no primary_domain, so there is nothing for Hunter to search."""
    rows = [{"First Name": "John", "Last Name": "Roe", "Company": "Acme"}]
    job_id = _seed_job(db, rows, MAPPING)
    summary = asyncio.run(runner.resolve_rows(db, job_id, POLICY))
    assert summary["to_lookup"] == 0
    assert summary["needs_domain"] == 1
    row = db.execute("SELECT * FROM enrichment_rows WHERE job_id = ?", (job_id,)).fetchone()
    assert row["hunter_status"] == "skipped"


def test_resolve_skips_an_already_verified_person(db):
    rows = [{"First Name": "Existing", "Last Name": "Person", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING)
    summary = asyncio.run(runner.resolve_rows(db, job_id, POLICY))
    assert summary["to_lookup"] == 0
    assert summary["skip_reasons"].get("already_verified") == 1
    assert summary["matched_existing"] == 1


def test_profile_enrichment_doubles_the_estimate(db):
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING, enrich_profile=True)
    summary = asyncio.run(runner.resolve_rows(db, job_id, POLICY))
    assert summary["credits_estimated"] == 2


def test_resolve_without_mapping_raises(db):
    job_id = runner.create_job(
        db, filename="c.csv", stored_path="/tmp/c.csv", file_sha256="x",
        source_type=SOURCE_SPREADSHEET, enrich_profile=False,
    )
    runner.store_rows(db, job_id, [{"A": "1"}])
    with pytest.raises(ValueError, match="mapping"):
        asyncio.run(runner.resolve_rows(db, job_id, POLICY))


# ---------------------------------------------------------------------------
# Fan-out
# ---------------------------------------------------------------------------


def test_run_job_fills_emails_and_auto_accepts(db):
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    def handler(request):
        return httpx.Response(200, json=_finder("jane.doe@cftc.gov"))

    async def go():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    result = asyncio.run(go())
    assert result["status"] == runner.STATUS_AWAITING_REVIEW
    assert result["credits_spent"] == 1

    row = db.execute("SELECT * FROM enrichment_rows WHERE job_id = ?", (job_id,)).fetchone()
    assert row["hunter_email"] == "jane.doe@cftc.gov"
    assert row["hunter_status"] == "found"
    assert row["review_status"] == "auto_accepted"
    assert row["write_action"] == "create"
    payload = json.loads(row["proposed_data"])
    assert payload["email"] == "jane.doe@cftc.gov"
    assert payload["source"] == "hunter"


def test_low_score_lands_in_review_not_auto_accept(db):
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    def handler(request):
        return httpx.Response(200, json=_finder("guess@cftc.gov", score=60))

    async def go():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    asyncio.run(go())
    row = db.execute("SELECT * FROM enrichment_rows WHERE job_id = ?", (job_id,)).fetchone()
    assert row["review_status"] == "pending"
    assert row["error_detail"] == "below_auto_accept_threshold"


def test_egress_gate_blocks_the_run(db):
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING, ack=False)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    def handler(request):  # pragma: no cover - must not be reached
        raise AssertionError("no Hunter call may happen before egress is acknowledged")

    async def go():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    with pytest.raises(PermissionError):
        asyncio.run(go())


def test_credit_cap_pauses_the_job(db):
    rows = [
        {"First Name": f"Person{i}", "Last Name": "Test", "Company": "CFTC"}
        for i in range(5)
    ]
    job_id = _seed_job(db, rows, MAPPING, cap=2)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=_finder(f"p{len(calls)}@cftc.gov"))

    async def go():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    result = asyncio.run(go())
    assert result["status"] == runner.STATUS_PAUSED
    assert result["credits_spent"] <= 2, "must not overrun the cap"
    assert len(calls) <= 2
    job = runner.get_job(db, job_id)
    assert job["status"] == runner.STATUS_PAUSED


def test_paused_job_resumes_where_it_stopped(db):
    rows = [
        {"First Name": f"Person{i}", "Last Name": "Test", "Company": "CFTC"}
        for i in range(4)
    ]
    job_id = _seed_job(db, rows, MAPPING, cap=2)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    def handler(request):
        return httpx.Response(200, json=_finder("x@cftc.gov", score=95))

    async def first():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    asyncio.run(first())
    done_after_first = db.execute(
        "SELECT COUNT(*) c FROM enrichment_rows WHERE job_id = ? AND hunter_status != 'pending'",
        (job_id,),
    ).fetchone()["c"]
    assert done_after_first == 2

    # Raise the cap and resume.
    runner.acknowledge_egress(db, job_id, 10)

    async def second():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    result = asyncio.run(second())
    assert result["status"] == runner.STATUS_AWAITING_REVIEW
    remaining = db.execute(
        "SELECT COUNT(*) c FROM enrichment_rows WHERE job_id = ? AND hunter_status = 'pending'",
        (job_id,),
    ).fetchone()["c"]
    assert remaining == 0


def test_auth_error_fails_the_whole_job(db):
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    def handler(request):
        return httpx.Response(401, json={"errors": [{"details": "bad key"}]})

    async def go():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    result = asyncio.run(go())
    assert result["status"] == runner.STATUS_FAILED
    assert runner.get_job(db, job_id)["status"] == runner.STATUS_FAILED


def test_not_found_row_is_recorded_and_job_continues(db):
    rows = [
        {"First Name": "Ghost", "Last Name": "Person", "Company": "CFTC"},
        {"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"},
    ]
    job_id = _seed_job(db, rows, MAPPING)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    def handler(request):
        if "Ghost" in str(request.url):
            return httpx.Response(200, json={"data": {"email": None}})
        return httpx.Response(200, json=_finder("jane.doe@cftc.gov"))

    async def go():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    result = asyncio.run(go())
    assert result["status"] == runner.STATUS_AWAITING_REVIEW
    statuses = {
        r["full_name"]: r["hunter_status"]
        for r in db.execute(
            "SELECT full_name, hunter_status FROM enrichment_rows WHERE job_id = ?",
            (job_id,),
        )
    }
    assert statuses["Ghost Person"] == "not_found"
    assert statuses["Jane Doe"] == "found"


def test_progress_events_are_published(db):
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    events = []

    async def publish(name, payload):
        events.append((name, payload))

    def handler(request):
        return httpx.Response(200, json=_finder("jane.doe@cftc.gov"))

    async def go():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c, publish=publish)

    asyncio.run(go())
    names = [e[0] for e in events]
    assert "enrichment_progress" in names
    assert "enrichment_complete" in names


def test_cache_hit_across_two_jobs_costs_nothing(db):
    """The second upload of the same person must not spend a credit."""
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=_finder("jane.doe@cftc.gov"))

    async def go(job_id):
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    last = None
    for _ in range(2):
        job_id = _seed_job(db, rows, MAPPING)
        asyncio.run(runner.resolve_rows(db, job_id, POLICY))
        last = asyncio.run(go(job_id))

    assert len(calls) == 1, "second job should be served entirely from cache"
    assert last["credits_spent"] == 0


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------


def _commit_job(db, job_id, monkeypatch, captured):
    async def fake_post_batch(operations, source=None, source_metadata=None,
                              idempotency_key=None):
        captured["operations"] = operations
        captured["source"] = source
        captured["idempotency_key"] = idempotency_key
        results = []
        for op in operations:
            if op["op"] == "insert":
                results.append({"op": "insert", "table": op["table"],
                                "record_id": "new-person-id",
                                "client_id": op.get("client_id"),
                                "previous_data": None})
            else:
                results.append({"op": op["op"], "table": op["table"],
                                "record_id": op.get("record_id"),
                                "previous_data": {"email": "old@cftc.gov"}})
        return {"results": results}

    monkeypatch.setattr(committer, "post_batch", fake_post_batch)
    return asyncio.run(committer.commit_job(db, job_id, POLICY))


def test_commit_writes_accepted_rows(db, monkeypatch):
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    def handler(request):
        return httpx.Response(200, json=_finder("jane.doe@cftc.gov"))

    async def go():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    asyncio.run(go())

    captured = {}
    result = _commit_job(db, job_id, monkeypatch, captured)
    assert result["committed"] == 1
    assert captured["source"] == "hunter"
    insert_ops = [o for o in captured["operations"] if o["op"] == "insert"]
    assert len(insert_ops) == 1
    assert insert_ops[0]["table"] == "people"

    row = db.execute("SELECT * FROM enrichment_rows WHERE job_id = ?", (job_id,)).fetchone()
    assert row["review_status"] == "committed"
    assert row["matched_person_id"] == "new-person-id"

    wb = db.execute(
        "SELECT * FROM enrichment_writebacks WHERE job_id = ?", (job_id,)
    ).fetchone()
    assert wb["target_table"] == "people"
    assert wb["write_type"] == "create"
    assert runner.get_job(db, job_id)["status"] == runner.STATUS_COMPLETE


def test_commit_with_nothing_accepted_is_a_noop(db, monkeypatch):
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))
    captured = {}
    result = _commit_job(db, job_id, monkeypatch, captured)
    assert result["committed"] == 0


def test_commit_learns_org_domains(db, monkeypatch):
    """A row whose org had no domain teaches the org, making reruns cheaper."""
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "Acme",
             "Email": "jane@acme.com"}]
    mapping = dict(MAPPING)
    mapping["Email"] = "email"
    job_id = _seed_job(db, rows, mapping)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))
    # Email already in the sheet, so no Hunter call; accept it manually.
    asyncio.run(runner.build_proposals(db, job_id, POLICY))
    db.execute(
        "UPDATE enrichment_rows SET review_status = 'accepted' WHERE job_id = ?",
        (job_id,),
    )
    db.commit()

    captured = {}
    _commit_job(db, job_id, monkeypatch, captured)
    org_ops = [o for o in captured["operations"] if o["table"] == "organizations"]
    assert org_ops, "expected a primary_domain writeback for Acme"
    assert org_ops[0]["data"]["primary_domain"] == "acme.com"


def test_idempotency_key_is_stable_for_the_same_rows(db):
    rows = [{"id": "r1"}, {"id": "r2"}]
    a = committer._idempotency_key("job1", rows)
    b = committer._idempotency_key("job1", list(reversed(rows)))
    assert a == b, "key must not depend on row order"
    c = committer._idempotency_key("job1", [{"id": "r1"}])
    assert a != c, "a different accepted set must get a different key"


def test_commit_failure_returns_job_to_review(db, monkeypatch):
    from app.writeback.tracker_client import TrackerBatchError

    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    def handler(request):
        return httpx.Response(200, json=_finder("jane.doe@cftc.gov"))

    async def go():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    asyncio.run(go())

    async def failing_post_batch(*a, **kw):
        raise TrackerBatchError(500, "server_error", "tracker exploded")

    monkeypatch.setattr(committer, "post_batch", failing_post_batch)
    with pytest.raises(TrackerBatchError):
        asyncio.run(committer.commit_job(db, job_id, POLICY))
    job = runner.get_job(db, job_id)
    assert job["status"] == runner.STATUS_AWAITING_REVIEW
    assert "tracker exploded" in (job["error_message"] or "")


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------


def test_undo_soft_deletes_created_people(db, monkeypatch):
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    job_id = _seed_job(db, rows, MAPPING)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    def handler(request):
        return httpx.Response(200, json=_finder("jane.doe@cftc.gov"))

    async def go():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    asyncio.run(go())
    _commit_job(db, job_id, monkeypatch, {})

    undo_ops = {}

    async def fake_post_batch(operations, **kw):
        undo_ops["operations"] = operations
        return {"results": []}

    monkeypatch.setattr(committer, "post_batch", fake_post_batch)
    result = asyncio.run(committer.undo_job(db, job_id))
    assert result["reversed"] == 1
    assert undo_ops["operations"][0]["op"] == "delete"
    assert undo_ops["operations"][0]["table"] == "people"
    wb = db.execute(
        "SELECT reversed FROM enrichment_writebacks WHERE job_id = ?", (job_id,)
    ).fetchone()
    assert wb["reversed"] == 1


def test_undo_with_nothing_to_reverse(db):
    job_id = _seed_job(db, [{"First Name": "A", "Last Name": "B", "Company": "CFTC"}],
                       MAPPING)
    result = asyncio.run(committer.undo_job(db, job_id))
    assert result["reversed"] == 0


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_preserves_original_columns_and_every_row(db):
    rows = [
        {"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC", "Notes": "keep me"},
        {"First Name": "Ghost", "Last Name": "Person", "Company": "CFTC", "Notes": ""},
    ]
    job_id = _seed_job(db, rows, MAPPING)
    asyncio.run(runner.resolve_rows(db, job_id, POLICY))

    def handler(request):
        if "Ghost" in str(request.url):
            return httpx.Response(200, json={"data": {"email": None}})
        return httpx.Response(200, json=_finder("jane.doe@cftc.gov"))

    async def go():
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    asyncio.run(go())

    content, filename, media_type = export.export_job(db, job_id)
    text = content.decode("utf-8-sig")
    header = text.splitlines()[0]

    assert filename == "contacts_enriched.csv"
    assert "text/csv" in media_type
    # Original columns first, in their original order.
    assert header.startswith("First Name,Last Name,Company,Notes")
    for col in export.APPENDED_COLUMNS:
        assert col in header
    # Both rows present, including the not-found one.
    body = text.splitlines()[1:]
    assert len(body) == 2
    assert "keep me" in text
    assert "jane.doe@cftc.gov" in text
    assert any("Ghost" in line for line in body), "not-found rows must still appear"


def test_export_xlsx_when_upload_was_xlsx(db):
    pytest.importorskip("openpyxl")
    job_id = runner.create_job(
        db, filename="contacts.xlsx", stored_path="/tmp/c.xlsx", file_sha256="x",
        source_type=SOURCE_SPREADSHEET, enrich_profile=False,
    )
    runner.store_rows(db, job_id, [{"First Name": "Jane", "Last Name": "Doe"}])
    content, filename, media_type = export.export_job(db, job_id)
    assert filename.endswith(".xlsx")
    assert "spreadsheetml" in media_type
    assert content[:2] == b"PK", "xlsx is a zip container"


def test_export_format_can_be_forced(db):
    job_id = runner.create_job(
        db, filename="contacts.xlsx", stored_path="/tmp/c.xlsx", file_sha256="x",
        source_type=SOURCE_SPREADSHEET, enrich_profile=False,
    )
    runner.store_rows(db, job_id, [{"A": "1"}])
    _, filename, _ = export.export_job(db, job_id, fmt="csv")
    assert filename.endswith(".csv")


def test_export_unknown_job_raises(db):
    with pytest.raises(ValueError):
        export.export_job(db, "nope")


# ---------------------------------------------------------------------------
# Credit cap under concurrency — regression guard
# ---------------------------------------------------------------------------


def test_credit_cap_holds_under_high_concurrency(db):
    """Regression: checking spent-so-far instead of reserving let every
    concurrent worker pass the cap check while spent was still stale, spending
    up to `max_concurrency` extra credits. The cap must be a hard ceiling."""
    rows = [
        {"First Name": f"Unique{i}", "Last Name": f"Name{i}", "Company": "CFTC"}
        for i in range(30)
    ]
    policy = json.loads(json.dumps(POLICY))
    policy["enrichment_policy"]["max_concurrency"] = 10
    cap = 4

    job_id = _seed_job(db, rows, MAPPING, cap=cap)
    asyncio.run(runner.resolve_rows(db, job_id, policy))

    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=_finder(f"u{len(calls)}@cftc.gov"))

    async def go():
        async with _mock_hunter(handler, policy) as c:
            return await runner.run_job(db, job_id, policy, client=c)

    result = asyncio.run(go())
    assert result["status"] == runner.STATUS_PAUSED
    assert len(calls) <= cap, f"spent {len(calls)} credits against a cap of {cap}"
    assert result["credits_spent"] <= cap
    assert runner.get_job(db, job_id)["credits_spent"] <= cap


def test_cached_rows_do_not_consume_the_credit_cap(db):
    """A cache hit costs no credit, so it must not eat the budget either."""
    rows = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}]
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=_finder("jane.doe@cftc.gov"))

    # Warm the cache with a first job.
    first = _seed_job(db, rows, MAPPING, cap=1)
    asyncio.run(runner.resolve_rows(db, first, POLICY))

    async def run(job_id):
        async with _mock_hunter(handler) as c:
            return await runner.run_job(db, job_id, POLICY, client=c)

    asyncio.run(run(first))
    assert len(calls) == 1

    # A second job with a cap of 1 and 3 cached rows should complete, not pause,
    # because none of those rows spends anything.
    rows3 = [{"First Name": "Jane", "Last Name": "Doe", "Company": "CFTC"}] * 3
    second = _seed_job(db, rows3, MAPPING, cap=1)
    asyncio.run(runner.resolve_rows(db, second, POLICY))
    result = asyncio.run(run(second))
    assert len(calls) == 1, "all three rows should be cache hits"
    assert result["status"] == runner.STATUS_AWAITING_REVIEW
    assert result["credits_spent"] == 0

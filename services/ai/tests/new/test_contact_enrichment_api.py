"""Contact enrichment API contracts.

Covers the gates that protect real money and real people: the Hunter key check,
the row cap, the mapping requirement, and the third-party egress acknowledgement.
No test here makes a network call.
"""

import io

import pytest
from app.enrichment import committer, runner
from app.enrichment.parsing import SOURCE_LINKEDIN

BASE = "/ai/api/enrichment"

CSV = (
    b"First Name,Last Name,Company\n"
    b"Jane,Doe,CFTC\n"
    b"John,Roe,Acme\n"
)

LINKEDIN_CSV = (
    b"First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
    b"Jane,Doe,https://www.linkedin.com/in/janedoe,,Acme Corp,Counsel,01 Jan 2024\n"
)

TRACKER_CONTEXT = {
    "people": [],
    "organizations": [
        {"id": "o1", "name": "Commodity Futures Trading Commission",
         "short_name": "CFTC", "primary_domain": "cftc.gov"},
    ],
}


@pytest.fixture(autouse=True)
def _configure(monkeypatch):
    """Pretend a Hunter key is configured, and never touch the tracker."""
    monkeypatch.setattr("app.routers.contact_enrichment.HUNTER_API_KEY", "test-key")

    async def fake_context():
        return TRACKER_CONTEXT

    monkeypatch.setattr(runner, "fetch_tracker_context", fake_context)


def _upload(client, content=CSV, name="contacts.csv", **params):
    return client.post(
        f"{BASE}/jobs",
        files={"file": (name, io.BytesIO(content), "text/csv")},
        params=params,
    )


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def test_status_reports_configuration(client):
    r = client.get(f"{BASE}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["api_key_configured"] is True
    assert body["auto_accept_score"] == 90
    assert body["require_egress_acknowledgement"] is True


def test_status_works_without_a_key_so_the_ui_can_explain(client, monkeypatch):
    monkeypatch.setattr("app.routers.contact_enrichment.HUNTER_API_KEY", "")
    r = client.get(f"{BASE}/status")
    assert r.status_code == 200
    assert r.json()["api_key_configured"] is False


def test_upload_refused_without_a_key(client, monkeypatch):
    monkeypatch.setattr("app.routers.contact_enrichment.HUNTER_API_KEY", "")
    r = _upload(client)
    assert r.status_code == 503
    assert "HUNTER_API_KEY" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def test_upload_parses_and_proposes_a_mapping(client):
    r = _upload(client)
    assert r.status_code == 200
    body = r.json()
    assert body["row_count"] == 2
    assert body["headers"] == ["First Name", "Last Name", "Company"]
    assert body["proposed_mapping"]["First Name"] == "first_name"
    assert body["proposed_mapping"]["Company"] == "org_name"
    assert body["mapping_problems"] == []
    assert len(body["preview"]) == 2


def test_linkedin_export_is_detected_automatically(client):
    """The preset should apply even when the caller does not say so."""
    r = _upload(client, LINKEDIN_CSV, "Connections.csv")
    assert r.status_code == 200
    body = r.json()
    assert body["source_type"] == SOURCE_LINKEDIN
    assert body["proposed_mapping"]["URL"] == "linkedin_url"
    assert body["proposed_mapping"]["Email Address"] == "email"


def test_empty_file_is_rejected(client):
    r = _upload(client, b"")
    assert r.status_code == 400


def test_headers_only_file_is_rejected(client):
    r = _upload(client, b"First Name,Last Name,Company\n")
    assert r.status_code == 422
    assert "No data rows" in r.json()["detail"]


def test_garbage_file_is_rejected_without_spending(client):
    r = _upload(client, b"\x00\x01\x02 not a sheet", "junk.xlsx")
    assert r.status_code == 422


def test_unknown_source_type_is_rejected(client):
    r = _upload(client, source_type="telepathy")
    assert r.status_code == 400


def test_row_cap_is_enforced(client, monkeypatch):
    from app.routers import contact_enrichment as ce

    monkeypatch.setattr(ce, "_enrich_policy", lambda: {"enabled": True, "max_rows_per_job": 1})
    r = _upload(client)
    assert r.status_code == 422
    assert "exceeds the per-job limit" in r.json()["detail"]


def test_oversized_file_is_rejected(client, monkeypatch):
    from app.routers import contact_enrichment as ce

    monkeypatch.setattr(ce, "MAX_ENRICHMENT_UPLOAD_BYTES", 10)
    r = _upload(client)
    assert r.status_code == 413


def test_duplicate_upload_is_flagged_not_blocked(client):
    first = _upload(client)
    assert first.status_code == 200
    second = _upload(client)
    assert second.status_code == 200
    assert second.json()["duplicate_of"]["id"] == first.json()["job_id"]


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


def test_confirm_mapping_resolves_rows(client):
    job_id = _upload(client).json()["job_id"]
    r = client.put(
        f"{BASE}/jobs/{job_id}/mapping",
        json={"mapping": {"First Name": "first_name", "Last Name": "last_name",
                          "Company": "org_name"}},
    )
    assert r.status_code == 200
    resolution = r.json()["resolution"]
    assert resolution["total"] == 2
    # Jane is at CFTC (domain known); John is at Acme (no domain) so is skipped.
    assert resolution["to_lookup"] == 1
    assert resolution["needs_domain"] == 1


def test_mapping_without_a_name_is_rejected(client):
    job_id = _upload(client).json()["job_id"]
    r = client.put(
        f"{BASE}/jobs/{job_id}/mapping", json={"mapping": {"Company": "org_name"}}
    )
    assert r.status_code == 422
    assert "mapping_problems" in r.json()["detail"]


def test_empty_mapping_is_rejected(client):
    job_id = _upload(client).json()["job_id"]
    assert client.put(f"{BASE}/jobs/{job_id}/mapping", json={"mapping": {}}).status_code == 400


def test_mapping_on_unknown_job_is_404(client):
    r = client.put(f"{BASE}/jobs/nope/mapping", json={"mapping": {"A": "full_name"}})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Pre-flight and the egress gate
# ---------------------------------------------------------------------------


def _mapped_job(client):
    job_id = _upload(client).json()["job_id"]
    client.put(
        f"{BASE}/jobs/{job_id}/mapping",
        json={"mapping": {"First Name": "first_name", "Last Name": "last_name",
                          "Company": "org_name"}},
    )
    return job_id


def test_preflight_requires_a_confirmed_mapping(client):
    job_id = _upload(client).json()["job_id"]
    r = client.get(f"{BASE}/jobs/{job_id}/preflight")
    assert r.status_code == 409


def test_preflight_reports_cost_without_spending(client, monkeypatch):
    async def fake_account(self):
        return {"requests": {"searches": {"available": 500}}}

    monkeypatch.setattr(
        "app.enrichment.hunter_client.HunterClient.account", fake_account
    )
    job_id = _mapped_job(client)
    r = client.get(f"{BASE}/jobs/{job_id}/preflight")
    assert r.status_code == 200
    body = r.json()
    assert body["to_lookup"] == 1
    assert body["credits_estimated"] == 1
    assert body["credit_balance"] == 500
    assert body["sufficient_credits"] is True
    assert body["egress_acknowledged"] is False
    assert body["credits_spent"] == 0


def test_preflight_survives_hunter_being_unreachable(client, monkeypatch):
    from app.enrichment.hunter_client import HunterError

    async def failing_account(self):
        raise HunterError(0, "connection refused", retryable=True)

    monkeypatch.setattr(
        "app.enrichment.hunter_client.HunterClient.account", failing_account
    )
    job_id = _mapped_job(client)
    r = client.get(f"{BASE}/jobs/{job_id}/preflight")
    assert r.status_code == 200
    assert r.json()["balance_error"] == "connection refused"


def test_start_without_acknowledging_egress_is_refused(client):
    """The gate that stops contact names reaching a third party by accident."""
    job_id = _mapped_job(client)
    r = client.post(f"{BASE}/jobs/{job_id}/start", json={})
    assert r.status_code == 422
    assert "acknowledge_egress" in r.json()["detail"]


def test_start_requires_a_mapping(client):
    job_id = _upload(client).json()["job_id"]
    r = client.post(
        f"{BASE}/jobs/{job_id}/start", json={"acknowledge_egress": True}
    )
    assert r.status_code == 409


def test_start_rejects_a_nonpositive_credit_cap(client):
    job_id = _mapped_job(client)
    r = client.post(
        f"{BASE}/jobs/{job_id}/start",
        json={"acknowledge_egress": True, "credit_cap": 0},
    )
    assert r.status_code == 400


def test_start_rejects_a_nonnumeric_credit_cap(client):
    job_id = _mapped_job(client)
    r = client.post(
        f"{BASE}/jobs/{job_id}/start",
        json={"acknowledge_egress": True, "credit_cap": "lots"},
    )
    assert r.status_code == 400


def test_start_runs_the_job(client, monkeypatch):
    calls = []

    async def fake_run_job(db, job_id, policy=None, client=None, publish=None):
        calls.append(job_id)
        return {"status": runner.STATUS_AWAITING_REVIEW, "credits_spent": 1}

    monkeypatch.setattr(runner, "run_job", fake_run_job)
    job_id = _mapped_job(client)
    r = client.post(
        f"{BASE}/jobs/{job_id}/start",
        json={"acknowledge_egress": True, "credit_cap": 10},
    )
    assert r.status_code == 200
    assert r.json()["status"] == runner.STATUS_AWAITING_REVIEW
    assert calls == [job_id]


# ---------------------------------------------------------------------------
# Jobs and rows
# ---------------------------------------------------------------------------


def test_list_jobs(client):
    _upload(client)
    r = client.get(f"{BASE}/jobs")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_get_job_includes_counts(client):
    job_id = _mapped_job(client)
    r = client.get(f"{BASE}/jobs/{job_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == job_id
    assert isinstance(body["review_counts"], dict)
    assert isinstance(body["hunter_counts"], dict)
    assert isinstance(body["column_mapping"], dict)


def test_get_unknown_job_is_404(client):
    assert client.get(f"{BASE}/jobs/nope").status_code == 404


def test_preview_returns_headers_and_rows(client):
    job_id = _upload(client).json()["job_id"]
    r = client.get(f"{BASE}/jobs/{job_id}/preview")
    assert r.status_code == 200
    assert r.json()["headers"] == ["First Name", "Last Name", "Company"]
    assert len(r.json()["rows"]) == 2


def test_list_rows_filters_and_hides_raw_payload(client):
    job_id = _mapped_job(client)
    r = client.get(f"{BASE}/jobs/{job_id}/rows")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert "hunter_raw" not in items[0], "audit blob should not bloat the list view"
    assert isinstance(items[0]["raw_row"], dict)

    filtered = client.get(f"{BASE}/jobs/{job_id}/rows", params={"hunter_status": "skipped"})
    assert filtered.json()["total"] == 1


# ---------------------------------------------------------------------------
# Row actions
# ---------------------------------------------------------------------------


def _first_row_id(client, job_id):
    return client.get(f"{BASE}/jobs/{job_id}/rows").json()["items"][0]["id"]


def test_accept_and_reject_a_row(client):
    job_id = _mapped_job(client)
    row_id = _first_row_id(client, job_id)

    r = client.patch(f"{BASE}/rows/{row_id}", json={"action": "accept"})
    assert r.status_code == 200
    assert r.json()["review_status"] == "accepted"

    r = client.patch(f"{BASE}/rows/{row_id}", json={"action": "reject"})
    assert r.json()["review_status"] == "rejected"


def test_edit_a_row_merges_over_the_proposal(client):
    job_id = _mapped_job(client)
    row_id = _first_row_id(client, job_id)
    r = client.patch(
        f"{BASE}/rows/{row_id}",
        json={"action": "edit", "data": {"email": "corrected@cftc.gov"}},
    )
    assert r.status_code == 200
    assert r.json()["review_status"] == "edited"
    row = client.get(f"{BASE}/jobs/{job_id}/rows").json()["items"]
    edited = next(x for x in row if x["id"] == row_id)
    assert edited["edited_data"]["email"] == "corrected@cftc.gov"


def test_edit_cannot_write_fields_enrichment_does_not_own(client):
    """Enrichment must not be a backdoor into relationship or matter data."""
    job_id = _mapped_job(client)
    row_id = _first_row_id(client, job_id)
    r = client.patch(
        f"{BASE}/rows/{row_id}",
        json={"action": "edit", "data": {"relationship_category": "Direct report"}},
    )
    assert r.status_code == 422
    assert "not writable" in r.json()["detail"]


def test_set_domain_requeues_a_skipped_row(client):
    job_id = _mapped_job(client)
    rows = client.get(f"{BASE}/jobs/{job_id}/rows", params={"hunter_status": "skipped"})
    row_id = rows.json()["items"][0]["id"]
    r = client.patch(
        f"{BASE}/rows/{row_id}", json={"action": "set_domain", "domain": "acme.com"}
    )
    assert r.status_code == 200
    after = client.get(f"{BASE}/jobs/{job_id}/rows").json()["items"]
    target = next(x for x in after if x["id"] == row_id)
    assert target["domain"] == "acme.com"
    assert target["hunter_status"] == "pending", "row should be queued for lookup again"


def test_set_domain_rejects_junk(client):
    job_id = _mapped_job(client)
    row_id = _first_row_id(client, job_id)
    r = client.patch(
        f"{BASE}/rows/{row_id}", json={"action": "set_domain", "domain": "not a domain"}
    )
    assert r.status_code == 400


def test_unknown_row_action_is_rejected(client):
    job_id = _mapped_job(client)
    row_id = _first_row_id(client, job_id)
    r = client.patch(f"{BASE}/rows/{row_id}", json={"action": "explode"})
    assert r.status_code == 400


def test_patch_unknown_row_is_404(client):
    assert client.patch(f"{BASE}/rows/nope", json={"action": "accept"}).status_code == 404


def test_bulk_accept_only_takes_auto_accepted(client, db):
    job_id = _mapped_job(client)
    db.execute(
        "UPDATE enrichment_rows SET review_status = 'auto_accepted' WHERE job_id = ?",
        (job_id,),
    )
    db.commit()
    r = client.post(f"{BASE}/jobs/{job_id}/bulk-accept", json={})
    assert r.status_code == 200
    assert r.json()["accepted"] == 2


def test_bulk_accept_with_nothing_pre_approved(client):
    job_id = _mapped_job(client)
    assert client.post(f"{BASE}/jobs/{job_id}/bulk-accept", json={}).json()["accepted"] == 0


# ---------------------------------------------------------------------------
# Commit, undo, export
# ---------------------------------------------------------------------------


def test_commit_calls_the_committer(client, monkeypatch):
    job_id = _mapped_job(client)

    async def fake_commit(db, jid, policy=None):
        return {"committed": 2, "operations": 2}

    monkeypatch.setattr(committer, "commit_job", fake_commit)
    r = client.post(f"{BASE}/jobs/{job_id}/commit")
    assert r.status_code == 200
    assert r.json()["committed"] == 2


def test_commit_failure_surfaces_as_502(client, monkeypatch):
    job_id = _mapped_job(client)

    async def failing(db, jid, policy=None):
        raise RuntimeError("tracker down")

    monkeypatch.setattr(committer, "commit_job", failing)
    r = client.post(f"{BASE}/jobs/{job_id}/commit")
    assert r.status_code == 502


def test_undo_calls_the_committer(client, monkeypatch):
    job_id = _mapped_job(client)

    async def fake_undo(db, jid):
        return {"reversed": 1}

    monkeypatch.setattr(committer, "undo_job", fake_undo)
    assert client.post(f"{BASE}/jobs/{job_id}/undo").json()["reversed"] == 1


def test_export_returns_a_csv_attachment_with_every_row(client):
    job_id = _mapped_job(client)
    r = client.get(f"{BASE}/jobs/{job_id}/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "contacts_enriched.csv" in r.headers["content-disposition"]
    text = r.content.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0].startswith("First Name,Last Name,Company")
    assert "hunter_email" in lines[0]
    assert len(lines) == 3, "header plus both input rows"


def test_export_can_be_forced_to_xlsx(client):
    pytest.importorskip("openpyxl")
    job_id = _mapped_job(client)
    r = client.get(f"{BASE}/jobs/{job_id}/export", params={"fmt": "xlsx"})
    assert r.status_code == 200
    assert r.content[:2] == b"PK"


def test_export_unknown_job_is_404(client):
    assert client.get(f"{BASE}/jobs/nope/export").status_code == 404


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_pause_only_applies_to_a_running_job(client):
    job_id = _mapped_job(client)
    r = client.post(f"{BASE}/jobs/{job_id}/pause")
    assert r.status_code == 409


def test_cancel_marks_the_job_cancelled(client):
    job_id = _mapped_job(client)
    r = client.post(f"{BASE}/jobs/{job_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == runner.STATUS_CANCELLED
    assert client.get(f"{BASE}/jobs/{job_id}").json()["status"] == runner.STATUS_CANCELLED


def test_resume_refuses_a_job_that_is_not_paused(client):
    job_id = _mapped_job(client)
    client.post(f"{BASE}/jobs/{job_id}/cancel")
    r = client.post(f"{BASE}/jobs/{job_id}/resume", json={})
    assert r.status_code == 409

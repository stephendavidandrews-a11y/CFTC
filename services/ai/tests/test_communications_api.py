"""Tests for the /ai/api/communications endpoints.

Covers:
1. List — empty, with data, pagination, status filter, archived exclusion
2. Get detail — success, not-found, child records
3. Retry — success from error state, rejection from non-retryable state
4. Archive — success, already-archived idempotency
5. Unarchive — restores archived communication
6. Delete — removes communication and child records
"""
import uuid

PREFIX = "/ai/api/communications"


# ── Helpers ──

def _seed_communication(db, comm_id=None, status="complete", archived=False, source_type="audio"):
    """Insert a minimal communication row and return its ID."""
    cid = comm_id or str(uuid.uuid4())
    db.execute(
        """INSERT INTO communications
           (id, source_type, original_filename, processing_status, archived_at, created_at, updated_at)
           VALUES (?, ?, 'test.wav', ?, ?, datetime('now'), datetime('now'))""",
        (cid, source_type, status, "2026-01-01T00:00:00" if archived else None),
    )
    db.commit()
    return cid


def _seed_with_children(db, comm_id=None):
    """Seed a communication with audio_files, participants, transcripts, messages, artifacts."""
    cid = comm_id or str(uuid.uuid4())
    _seed_communication(db, cid, status="complete")

    # Audio file
    db.execute(
        "INSERT INTO audio_files (id, communication_id, file_path, original_filename, format) VALUES (?, ?, '/tmp/x.wav', 'x.wav', 'wav')",
        (str(uuid.uuid4()), cid),
    )
    # Participant
    db.execute(
        "INSERT INTO communication_participants (id, communication_id, speaker_label, proposed_name) VALUES (?, ?, 'SPEAKER_00', 'Alice')",
        (str(uuid.uuid4()), cid),
    )
    # Transcript
    db.execute(
        "INSERT INTO transcripts (id, communication_id, speaker_label, start_time, end_time, raw_text) VALUES (?, ?, 'SPEAKER_00', 0.0, 5.0, 'Hello world')",
        (str(uuid.uuid4()), cid),
    )
    # Message (email child)
    db.execute(
        """INSERT INTO communication_messages
           (id, communication_id, message_index, sender_email, subject, message_hash, is_new)
           VALUES (?, ?, 0, 'alice@example.com', 'Test', ?, 1)""",
        (str(uuid.uuid4()), cid, str(uuid.uuid4())),
    )
    # Artifact
    db.execute(
        """INSERT INTO communication_artifacts
           (id, communication_id, original_filename, file_path, mime_type, artifact_type)
           VALUES (?, ?, 'doc.pdf', '/tmp/doc.pdf', 'application/pdf', 'attachment')""",
        (str(uuid.uuid4()), cid),
    )
    db.commit()
    return cid


# ── 1. List: empty DB ──

def test_list_empty(client):
    resp = client.get(PREFIX)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


# ── 2. List: with data + pagination ──

def test_list_with_data_and_pagination(client, db):
    for i in range(5):
        _seed_communication(db, status="complete")

    # Default returns all 5
    resp = client.get(PREFIX)
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 5

    # Paginate: offset=2, limit=2
    resp = client.get(PREFIX, params={"offset": 2, "limit": 2})
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["offset"] == 2
    assert data["limit"] == 2


# ── 3. List: status filter ──

def test_list_status_filter(client, db):
    _seed_communication(db, status="pending")
    _seed_communication(db, status="complete")
    _seed_communication(db, status="error")

    resp = client.get(PREFIX, params={"status": "error"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["processing_status"] == "error"


# ── 4. List: archived excluded by default, included with flag ──

def test_list_excludes_archived(client, db):
    _seed_communication(db, status="complete")
    _seed_communication(db, status="complete", archived=True)

    # Default: only non-archived
    resp = client.get(PREFIX)
    assert resp.json()["total"] == 1

    # With include_archived=true
    resp = client.get(PREFIX, params={"include_archived": "true"})
    assert resp.json()["total"] == 2


# ── 5. Get detail: success with child records ──

def test_get_detail_with_children(client, db):
    cid = _seed_with_children(db)
    resp = client.get(f"{PREFIX}/{cid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == cid
    assert len(data["audio_files"]) == 1
    assert len(data["participants"]) == 1
    assert data["transcript_count"] == 1
    assert len(data["messages"]) == 1
    assert len(data["artifacts"]) == 1


# ── 6. Get detail: not found ──

def test_get_detail_not_found(client):
    resp = client.get(f"{PREFIX}/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── 7. Retry: success from error state ──

def test_retry_from_error(client, db):
    cid = str(uuid.uuid4())
    db.execute(
        """INSERT INTO communications
           (id, source_type, processing_status, error_stage, error_message, created_at, updated_at)
           VALUES (?, 'audio', 'error', 'extraction', 'LLM timeout', datetime('now'), datetime('now'))""",
        (cid,),
    )
    db.commit()

    resp = client.post(f"{PREFIX}/{cid}/retry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "retrying"
    assert data["from_stage"] == "extraction"
    assert data["previous_state"] == "error"

    # Verify DB was updated
    row = db.execute("SELECT processing_status, error_message FROM communications WHERE id = ?", (cid,)).fetchone()
    assert row["processing_status"] == "extraction"
    assert row["error_message"] is None


# ── 8. Retry: rejected for non-retryable state ──

def test_retry_rejected_for_complete(client, db):
    cid = _seed_communication(db, status="complete")
    resp = client.post(f"{PREFIX}/{cid}/retry")
    assert resp.status_code == 400
    body = resp.json()
    # Middleware may wrap the response; check both formats
    if "detail" in body:
        assert "invalid_state" in body["detail"]["error_type"]
    else:
        assert "invalid_state" in body.get("error", {}).get("message", "")


# ── 9. Archive + already-archived idempotency ──

def test_archive_and_idempotency(client, db):
    cid = _seed_communication(db, status="complete")

    # First archive
    resp = client.post(f"{PREFIX}/{cid}/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"

    # Verify DB
    row = db.execute("SELECT archived_at FROM communications WHERE id = ?", (cid,)).fetchone()
    assert row["archived_at"] is not None

    # Second archive is idempotent
    resp = client.post(f"{PREFIX}/{cid}/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "already_archived"


# ── 10. Unarchive ──

def test_unarchive(client, db):
    cid = _seed_communication(db, status="complete", archived=True)
    resp = client.post(f"{PREFIX}/{cid}/unarchive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "unarchived"

    row = db.execute("SELECT archived_at FROM communications WHERE id = ?", (cid,)).fetchone()
    assert row["archived_at"] is None


# ── 11. Delete removes communication and child records ──

def test_delete_communication(client, db):
    cid = _seed_with_children(db)

    resp = client.delete(f"{PREFIX}/{cid}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Communication gone
    row = db.execute("SELECT id FROM communications WHERE id = ?", (cid,)).fetchone()
    assert row is None

    # Child records gone
    assert db.execute("SELECT COUNT(*) as c FROM audio_files WHERE communication_id = ?", (cid,)).fetchone()["c"] == 0
    assert db.execute("SELECT COUNT(*) as c FROM communication_participants WHERE communication_id = ?", (cid,)).fetchone()["c"] == 0
    assert db.execute("SELECT COUNT(*) as c FROM transcripts WHERE communication_id = ?", (cid,)).fetchone()["c"] == 0


# ── 12. Delete: not found ──

def test_delete_not_found(client):
    resp = client.delete(f"{PREFIX}/{uuid.uuid4()}")
    assert resp.status_code == 404

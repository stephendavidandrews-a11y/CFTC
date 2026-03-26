"""Tests for the /ai/api/communications endpoints.

Covers:
1.  List — empty, with data, pagination, status filter, archived exclusion, source_type filter
2.  Get detail — success, not-found, child records, response shape
3.  Retry — success from error state, paused_budget state, rejection from non-retryable state
4.  Archive — success, already-archived idempotency, not-found
5.  Unarchive — restores archived communication, not-found
6.  Delete — removes communication and child records, not-found
7.  Undo — endpoint error/status mapping (invalid state, not found, no writebacks, conflict 409, force)
8.  Upload validation — bad format, empty body
9.  Audio streaming — not-found, missing file on disk
"""

import json
import uuid
from unittest.mock import patch, AsyncMock

PREFIX = "/ai/api/communications"


# ── Helpers ──


def _seed_communication(
    db, comm_id=None, status="complete", archived=False, source_type="audio"
):
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

    db.execute(
        "INSERT INTO audio_files (id, communication_id, file_path, original_filename, format) VALUES (?, ?, '/tmp/x.wav', 'x.wav', 'wav')",
        (str(uuid.uuid4()), cid),
    )
    db.execute(
        "INSERT INTO communication_participants (id, communication_id, speaker_label, proposed_name) VALUES (?, ?, 'SPEAKER_00', 'Alice')",
        (str(uuid.uuid4()), cid),
    )
    db.execute(
        "INSERT INTO transcripts (id, communication_id, speaker_label, start_time, end_time, raw_text) VALUES (?, ?, 'SPEAKER_00', 0.0, 5.0, 'Hello world')",
        (str(uuid.uuid4()), cid),
    )
    db.execute(
        """INSERT INTO communication_messages
           (id, communication_id, message_index, sender_email, subject, message_hash, is_new)
           VALUES (?, ?, 0, 'alice@example.com', 'Test', ?, 1)""",
        (str(uuid.uuid4()), cid, str(uuid.uuid4())),
    )
    db.execute(
        """INSERT INTO communication_artifacts
           (id, communication_id, original_filename, file_path, mime_type, artifact_type)
           VALUES (?, ?, 'doc.pdf', '/tmp/doc.pdf', 'application/pdf', 'attachment')""",
        (str(uuid.uuid4()), cid),
    )
    db.commit()
    return cid


def _seed_for_undo(db, comm_id=None, status="complete", add_writebacks=True):
    """Seed a communication with tracker_writebacks for undo testing.

    Also seeds a review_bundle (required FK for tracker_writebacks.bundle_id).
    """
    cid = comm_id or str(uuid.uuid4())
    _seed_communication(db, cid, status=status)

    if add_writebacks:
        bundle_id = str(uuid.uuid4())
        wb_id = str(uuid.uuid4())

        # review_bundle is required by tracker_writebacks FK
        db.execute(
            """INSERT INTO review_bundles
               (id, communication_id, bundle_type, status, created_at, updated_at)
               VALUES (?, ?, 'existing_matter', 'proposed', datetime('now'), datetime('now'))""",
            (bundle_id, cid),
        )
        db.execute(
            """INSERT INTO tracker_writebacks
               (id, communication_id, bundle_id, target_table, target_record_id,
                write_type, written_data, previous_data, reversed)
               VALUES (?, ?, ?, 'people', ?, 'insert', ?, NULL, 0)""",
            (
                wb_id,
                cid,
                bundle_id,
                str(uuid.uuid4()),
                json.dumps({"name": "Test Person", "email": "test@example.com"}),
            ),
        )
        db.commit()

    return cid


# ===================================================================
# 1. List endpoint
# ===================================================================


def test_list_empty(client):
    resp = client.get(PREFIX)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_with_data_and_pagination(client, db):
    for i in range(5):
        _seed_communication(db, status="complete")

    resp = client.get(PREFIX)
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 5

    resp = client.get(PREFIX, params={"offset": 2, "limit": 2})
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["offset"] == 2
    assert data["limit"] == 2


def test_list_status_filter(client, db):
    _seed_communication(db, status="pending")
    _seed_communication(db, status="complete")
    _seed_communication(db, status="error")

    resp = client.get(PREFIX, params={"status": "error"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["processing_status"] == "error"


def test_list_excludes_archived(client, db):
    _seed_communication(db, status="complete")
    _seed_communication(db, status="complete", archived=True)

    resp = client.get(PREFIX)
    assert resp.json()["total"] == 1

    resp = client.get(PREFIX, params={"include_archived": "true"})
    assert resp.json()["total"] == 2


def test_list_source_type_filter(client, db):
    _seed_communication(db, status="complete", source_type="audio")
    _seed_communication(db, status="complete", source_type="email")
    _seed_communication(db, status="complete", source_type="audio")

    resp = client.get(PREFIX, params={"source_type": "email"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["source_type"] == "email"


def test_list_response_shape(client, db):
    """Verify response shape has all expected top-level and item-level fields."""
    _seed_communication(db, status="complete")
    resp = client.get(PREFIX)
    data = resp.json()

    assert set(data.keys()) >= {"items", "total", "offset", "limit"}

    item = data["items"][0]
    expected_keys = {
        "id",
        "source_type",
        "processing_status",
        "created_at",
        "updated_at",
    }
    assert set(item.keys()) >= expected_keys


# ===================================================================
# 2. Detail endpoint
# ===================================================================


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


def test_get_detail_not_found(client):
    resp = client.get(f"{PREFIX}/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_detail_response_shape(client, db):
    """Verify detail response contains all expected structural fields."""
    cid = _seed_communication(db, status="complete")
    resp = client.get(f"{PREFIX}/{cid}")
    data = resp.json()
    expected = {
        "id",
        "source_type",
        "processing_status",
        "created_at",
        "updated_at",
        "audio_files",
        "participants",
        "transcript_count",
        "messages",
        "artifacts",
    }
    assert set(data.keys()) >= expected


# ===================================================================
# 3. Retry endpoint
# ===================================================================


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

    row = db.execute(
        "SELECT processing_status, error_message FROM communications WHERE id = ?",
        (cid,),
    ).fetchone()
    assert row["processing_status"] == "extraction"
    assert row["error_message"] is None


def test_retry_from_paused_budget(client, db):
    """Retry from paused_budget state should be accepted."""
    cid = str(uuid.uuid4())
    db.execute(
        """INSERT INTO communications
           (id, source_type, processing_status, error_stage, error_message, created_at, updated_at)
           VALUES (?, 'audio', 'paused_budget', 'extraction', 'Budget exceeded', datetime('now'), datetime('now'))""",
        (cid,),
    )
    db.commit()

    resp = client.post(f"{PREFIX}/{cid}/retry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "retrying"
    assert data["previous_state"] == "paused_budget"


def test_retry_rejected_for_complete(client, db):
    cid = _seed_communication(db, status="complete")
    resp = client.post(f"{PREFIX}/{cid}/retry")
    assert resp.status_code == 400
    body = resp.json()
    detail = body.get("detail", body)
    assert "invalid_state" in str(detail)


def test_retry_not_found(client):
    resp = client.post(f"{PREFIX}/{uuid.uuid4()}/retry")
    assert resp.status_code == 404


# ===================================================================
# 4. Archive / Unarchive endpoints
# ===================================================================


def test_archive_and_idempotency(client, db):
    cid = _seed_communication(db, status="complete")

    resp = client.post(f"{PREFIX}/{cid}/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"

    row = db.execute(
        "SELECT archived_at FROM communications WHERE id = ?", (cid,)
    ).fetchone()
    assert row["archived_at"] is not None

    resp = client.post(f"{PREFIX}/{cid}/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "already_archived"


def test_archive_not_found(client):
    resp = client.post(f"{PREFIX}/{uuid.uuid4()}/archive")
    assert resp.status_code == 404


def test_unarchive(client, db):
    cid = _seed_communication(db, status="complete", archived=True)
    resp = client.post(f"{PREFIX}/{cid}/unarchive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "unarchived"

    row = db.execute(
        "SELECT archived_at FROM communications WHERE id = ?", (cid,)
    ).fetchone()
    assert row["archived_at"] is None


def test_unarchive_not_found(client):
    resp = client.post(f"{PREFIX}/{uuid.uuid4()}/unarchive")
    assert resp.status_code == 404


# ===================================================================
# 5. Delete endpoint
# ===================================================================


def test_delete_communication(client, db):
    cid = _seed_with_children(db)

    resp = client.delete(f"{PREFIX}/{cid}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    row = db.execute("SELECT id FROM communications WHERE id = ?", (cid,)).fetchone()
    assert row is None

    assert (
        db.execute(
            "SELECT COUNT(*) as c FROM audio_files WHERE communication_id = ?", (cid,)
        ).fetchone()["c"]
        == 0
    )
    assert (
        db.execute(
            "SELECT COUNT(*) as c FROM communication_participants WHERE communication_id = ?",
            (cid,),
        ).fetchone()["c"]
        == 0
    )
    assert (
        db.execute(
            "SELECT COUNT(*) as c FROM transcripts WHERE communication_id = ?", (cid,)
        ).fetchone()["c"]
        == 0
    )


def test_delete_not_found(client):
    resp = client.delete(f"{PREFIX}/{uuid.uuid4()}")
    assert resp.status_code == 404


# ===================================================================
# 6. Undo endpoint — HTTP status mapping
# ===================================================================


def test_undo_not_found(client):
    """Undo on nonexistent communication should return 404."""
    resp = client.post(f"{PREFIX}/{uuid.uuid4()}/undo")
    assert resp.status_code == 404
    detail = resp.json().get("detail", resp.json())
    assert "invalid_communication" in str(detail)


def test_undo_invalid_state(client, db):
    """Undo on a non-complete communication should return 400."""
    cid = _seed_communication(db, status="pending")
    resp = client.post(f"{PREFIX}/{cid}/undo")
    assert resp.status_code == 400
    detail = resp.json().get("detail", resp.json())
    assert "not_undoable_state" in str(detail)


def test_undo_no_writebacks(client, db):
    """Undo on a complete communication with no writebacks should return 400."""
    cid = _seed_communication(db, status="complete")
    resp = client.post(f"{PREFIX}/{cid}/undo")
    assert resp.status_code == 400
    detail = resp.json().get("detail", resp.json())
    assert "no_writebacks" in str(detail)


@patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
@patch("app.writeback.undo._tracker_delete", new_callable=AsyncMock)
def test_undo_success(mock_delete, mock_get, client, db):
    """Undo with a valid insert writeback and no conflicts should succeed."""
    mock_get.return_value = {"name": "Test Person", "email": "test@example.com"}
    mock_delete.return_value = True

    cid = _seed_for_undo(db, status="complete", add_writebacks=True)
    resp = client.post(f"{PREFIX}/{cid}/undo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "undone"
    assert data["reversed_count"] >= 1

    row = db.execute(
        "SELECT processing_status FROM communications WHERE id = ?", (cid,)
    ).fetchone()
    assert row["processing_status"] == "reviewed"


@patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
def test_undo_conflict_returns_409(mock_get, client, db):
    """Undo with conflict should return 409 when not forced."""
    mock_get.return_value = {"name": "Human Changed This", "email": "test@example.com"}

    cid = _seed_for_undo(db, status="complete", add_writebacks=True)
    resp = client.post(f"{PREFIX}/{cid}/undo")
    assert resp.status_code == 409
    detail = resp.json().get("detail", resp.json())
    assert "conflict" in str(detail).lower()


@patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
@patch("app.writeback.undo._tracker_delete", new_callable=AsyncMock)
def test_undo_force_overrides_conflict(mock_delete, mock_get, client, db):
    """Undo with force=true should succeed even with conflicts."""
    mock_get.return_value = {"name": "Human Changed This", "email": "test@example.com"}
    mock_delete.return_value = True

    cid = _seed_for_undo(db, status="complete", add_writebacks=True)
    resp = client.post(f"{PREFIX}/{cid}/undo", params={"force": "true"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "undone"
    assert data["forced"] is True


# ===================================================================
# 7. Upload validation
# ===================================================================


def test_audio_upload_rejects_bad_format(client):
    """Upload with unsupported format should return 400."""
    resp = client.post(
        f"{PREFIX}/audio-upload",
        files={"audio": ("test.exe", b"not-audio-data", "application/octet-stream")},
        data={"source_type": "audio_upload"},
    )
    assert resp.status_code == 400
    detail = resp.json().get("detail", resp.json())
    assert "validation_failure" in str(detail) or "Unsupported" in str(detail)


def test_audio_upload_rejects_empty_file(client):
    """Upload with empty file should return 400."""
    resp = client.post(
        f"{PREFIX}/audio-upload",
        files={"audio": ("test.wav", b"", "audio/wav")},
        data={"source_type": "audio_upload"},
    )
    assert resp.status_code == 400
    detail = resp.json().get("detail", resp.json())
    assert "Empty" in str(detail) or "validation_failure" in str(detail)


def test_email_upload_rejects_bad_format(client):
    """Email upload with unsupported format should return 400."""
    resp = client.post(
        f"{PREFIX}/email-upload",
        files={"email_file": ("test.pdf", b"not-an-email", "application/pdf")},
    )
    assert resp.status_code == 400
    detail = resp.json().get("detail", resp.json())
    assert "validation_failure" in str(detail) or "Unsupported" in str(detail)


def test_email_upload_rejects_empty_file(client):
    """Email upload with empty file should return 400."""
    resp = client.post(
        f"{PREFIX}/email-upload",
        files={"email_file": ("test.eml", b"", "message/rfc822")},
    )
    assert resp.status_code == 400
    detail = resp.json().get("detail", resp.json())
    assert "Empty" in str(detail) or "validation_failure" in str(detail)


# ===================================================================
# 8. Audio streaming endpoint
# ===================================================================


def test_audio_stream_not_found_no_communication(client):
    """Audio stream for nonexistent communication returns 404."""
    resp = client.get(f"{PREFIX}/{uuid.uuid4()}/audio")
    assert resp.status_code == 404


def test_audio_stream_not_found_no_audio_file(client, db):
    """Audio stream for communication with no audio files returns 404."""
    cid = _seed_communication(db, status="complete")
    resp = client.get(f"{PREFIX}/{cid}/audio")
    assert resp.status_code == 404


def test_audio_stream_file_missing_on_disk(client, db):
    """Audio stream when file path does not exist on disk returns 404."""
    cid = _seed_communication(db, status="complete")
    db.execute(
        "INSERT INTO audio_files (id, communication_id, file_path, original_filename, format) VALUES (?, ?, '/nonexistent/path/audio.wav', 'audio.wav', 'wav')",
        (str(uuid.uuid4()), cid),
    )
    db.commit()

    resp = client.get(f"{PREFIX}/{cid}/audio")
    assert resp.status_code == 404
    detail = resp.json().get("detail", resp.json())
    assert "missing" in str(detail).lower() or "not_found" in str(detail).lower()

"""Tests for the /ai/api/health endpoint.

Covers:
1. Basic health response shape and version
2. Empty queue counts (fresh DB)
3. Queue counts with seeded communications
4. Spend / budget tracking from llm_usage
5. Budget-paused flag when spend exceeds budget
"""

import uuid

PREFIX = "/ai/api"


# ── 1. Basic health shape ──


def test_health_returns_ok(client):
    resp = client.get(f"{PREFIX}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "cftc-ai"
    assert "version" in data
    assert "timestamp" in data
    assert "queue" in data
    assert "spend" in data


# ── 2. Empty DB: queue is empty dict, spend is zero ──


def test_health_empty_db(client):
    data = client.get(f"{PREFIX}/health").json()
    assert data["queue"] == {}
    assert data["spend"]["today_usd"] == 0.0
    assert data["spend"]["paused"] is False


# ── 3. Queue counts reflect communication statuses ──


def test_health_queue_counts(client, db):
    # Seed communications in various statuses
    for status, count in [("pending", 3), ("processing", 2), ("error", 1)]:
        for _ in range(count):
            db.execute(
                "INSERT INTO communications (id, source_type, processing_status) VALUES (?, 'audio', ?)",
                (str(uuid.uuid4()), status),
            )
    db.commit()

    data = client.get(f"{PREFIX}/health").json()
    assert data["queue"]["pending"] == 3
    assert data["queue"]["processing"] == 2
    assert data["queue"]["error"] == 1


# ── 4. Spend tracking from llm_usage ──


def test_health_spend_tracking(client, db):
    comm_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO communications (id, source_type, processing_status) VALUES (?, 'audio', 'complete')",
        (comm_id,),
    )
    # Insert two LLM usage rows for today
    db.execute(
        "INSERT INTO llm_usage (communication_id, stage, model, input_tokens, output_tokens, cost_usd) VALUES (?, 'extraction', 'sonnet', 1000, 500, 1.25)",
        (comm_id,),
    )
    db.execute(
        "INSERT INTO llm_usage (communication_id, stage, model, input_tokens, output_tokens, cost_usd) VALUES (?, 'enrichment', 'haiku', 200, 100, 0.50)",
        (comm_id,),
    )
    db.commit()

    data = client.get(f"{PREFIX}/health").json()
    assert data["spend"]["today_usd"] == 1.75
    assert data["spend"]["budget_remaining_usd"] == round(
        data["spend"]["daily_budget_usd"] - 1.75, 4
    )
    assert data["spend"]["paused"] is False


# ── 5. Budget-paused when spend meets or exceeds daily budget ──


def test_health_budget_paused(client, db):
    comm_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO communications (id, source_type, processing_status) VALUES (?, 'audio', 'complete')",
        (comm_id,),
    )
    # Blow past the default $10 budget
    db.execute(
        "INSERT INTO llm_usage (communication_id, stage, model, input_tokens, output_tokens, cost_usd) VALUES (?, 'extraction', 'opus', 50000, 20000, 15.00)",
        (comm_id,),
    )
    db.commit()

    data = client.get(f"{PREFIX}/health").json()
    assert data["spend"]["today_usd"] == 15.0
    assert data["spend"]["paused"] is True
    assert data["spend"]["budget_remaining_usd"] < 0

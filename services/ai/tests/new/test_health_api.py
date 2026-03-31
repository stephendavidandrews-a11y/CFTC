"""Tests for the /ai/api/health and /ai/api/costs endpoints.

Covers:
1. Basic public health response shape
2. Empty queue counts (fresh DB)
3. Queue counts with seeded communications
4. Protected cost tracking from llm_usage
5. Budget handling on the costs endpoint
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
    assert "spend" not in data
    assert "disk" not in data


# ── 2. Empty DB: queue is empty dict, spend is zero ──


def test_health_empty_db(client):
    data = client.get(f"{PREFIX}/health").json()
    assert data["queue"] == {}
    assert "spend" not in data


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


def test_costs_spend_tracking(client, db):
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

    data = client.get(f"{PREFIX}/costs").json()
    assert data["today_usd"] == 1.75
    assert data["daily_budget_usd"] >= 1.75
    assert data["daily_budget_usd"] - data["today_usd"] == round(
        data["daily_budget_usd"] - 1.75, 4
    )


# ── 5. Budget-paused when spend meets or exceeds daily budget ──


def test_costs_budget_threshold(client, db):
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

    data = client.get(f"{PREFIX}/costs").json()
    assert data["today_usd"] == 15.0
    assert data["daily_budget_usd"] < data["today_usd"]

"""Intake authentication tests — verify HTTPBasic on all API routers."""


def test_health_unauthenticated(client):
    """Health endpoint does NOT require auth."""
    resp = client.get("/intake/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "operational"


def test_metrics_unauthenticated(client):
    """Metrics endpoint does NOT require auth."""
    resp = client.get("/intake/api/metrics")
    assert resp.status_code == 200
    assert "endpoints" in resp.json()


def test_conversations_no_auth_returns_401(client):
    """API endpoint without credentials returns 401."""
    resp = client.get("/intake/api/conversations")
    assert resp.status_code == 401


def test_conversations_bad_auth_returns_401(client, bad_auth_headers):
    """API endpoint with wrong credentials returns 401."""
    resp = client.get("/intake/api/conversations", headers=bad_auth_headers)
    assert resp.status_code == 401


def test_conversations_good_auth_succeeds(client, auth_headers):
    """API endpoint with valid credentials succeeds."""
    resp = client.get("/intake/api/conversations", headers=auth_headers)
    assert resp.status_code == 200


def test_pipeline_no_auth_returns_401(client):
    """Pipeline endpoint without credentials returns 401."""
    resp = client.get("/intake/api/pipeline/status")
    assert resp.status_code == 401


def test_pipeline_good_auth_succeeds(client, auth_headers):
    """Pipeline endpoint with valid credentials succeeds."""
    resp = client.get("/intake/api/pipeline/status", headers=auth_headers)
    # 200 or 404 both prove auth passed (not 401)
    assert resp.status_code != 401


def test_response_headers_present(client, auth_headers):
    """Verify X-Request-ID and X-API-Version headers on responses."""
    resp = client.get("/intake/api/health")
    assert "x-request-id" in resp.headers
    assert resp.headers.get("x-api-version") == "1.0"

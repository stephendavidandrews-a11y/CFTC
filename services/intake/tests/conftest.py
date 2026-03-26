"""Intake test fixtures."""

import os
import sys
from pathlib import Path

import pytest

# Ensure intake service root is on sys.path
SERVICE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

# Set test credentials before importing app
os.environ["PIPELINE_USER"] = "testpipeline"
os.environ["PIPELINE_PASS"] = "testpipelinepass"
os.environ["APP_ENV"] = "development"


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient for intake service."""
    from main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers():
    """Valid auth headers for intake tests."""
    import base64

    creds = base64.b64encode(b"testpipeline:testpipelinepass").decode()
    return {"Authorization": f"Basic {creds}"}


@pytest.fixture(scope="session")
def bad_auth_headers():
    """Invalid auth headers."""
    import base64

    creds = base64.b64encode(b"wrong:wrong").decode()
    return {"Authorization": f"Basic {creds}"}

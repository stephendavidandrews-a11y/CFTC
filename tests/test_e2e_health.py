#!/usr/bin/env python3
"""
End-to-end health & contract tests for CFTC services.

Catches four classes of production bugs:
  1. Import failures   - missing imports, NameErrors in module scope
  2. Env var gaps       - plist missing vars the code requires
  3. API contract drift - consumer calls endpoint that provider lacks
  4. Ops health         - log bloat, missing rotation, disk pressure

Run:  python3 tests/test_e2e_health.py -v
  or: make test-e2e

To extend: add entries to the registries at the top of each section.
Each registry is a plain list - one line per service/module/endpoint/log.
"""

import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
from base64 import b64encode

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRACKER_AUTH = (
    os.environ.get("TRACKER_USER", "Stephen"),
    os.environ.get("TRACKER_PASS", "FreshHippo2022"),
)
AI_AUTH = (
    os.environ.get("AI_AUTH_USER", "Stephen"),
    os.environ.get("AI_AUTH_PASS", "FreshHippo2022"),
)


def _basic_auth_header(user: str, password: str) -> str:
    token = b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def _http_get(url, params=None, auth=None, timeout=10):
    """Minimal HTTP GET using only stdlib. Returns (status, parsed_json)."""
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = Request(url)
    if auth:
        req.add_header("Authorization", _basic_auth_header(*auth))
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except URLError as exc:
        return 0, str(exc)


# ===========================================================================
# Category 1: Import Smoke Tests
# ===========================================================================
# (service_subdir, module_dotpath)
# Add a line here for every critical module.
SERVICE_MODULES = [
    # -- AI service --
    ("services/ai", "app.main"),
    ("services/ai", "app.config"),
    ("services/ai", "app.jobs.daily_brief"),
    ("services/ai", "app.jobs.weekly_brief"),
    ("services/ai", "app.jobs.email_sender"),
    ("services/ai", "app.pipeline.orchestrator"),
    # -- Tracker service --
    ("services/tracker", "app.main"),
    ("services/tracker", "app.config"),
    ("services/tracker", "app.routers.matters"),
    ("services/tracker", "app.routers.system_events"),
    ("services/tracker", "app.routers.organizations"),
    ("services/tracker", "app.routers.people"),
    ("services/tracker", "app.routers.tasks"),
    ("services/tracker", "app.audit"),
]


class TestImportSmoke(unittest.TestCase):
    """Every critical module must import without errors."""

    def _run_import(self, service_dir, module):
        svc_path = PROJECT_ROOT / service_dir
        venv_python = svc_path / ".venv" / "bin" / "python3"
        if not venv_python.exists():
            self.skipTest(f"venv not found: {venv_python}")

        result = subprocess.run(
            [str(venv_python), "-c", f"import {module}"],
            cwd=str(svc_path),
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "APP_ENV": "test", "PYTHONPATH": str(svc_path)},
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Import failed for {module} in {service_dir}:\n"
            f"{result.stderr[-500:]}",
        )


# Dynamically generate a test method per module
def _make_import_test(svc_dir, mod):
    def test(self):
        self._run_import(svc_dir, mod)

    test.__doc__ = f"import {mod} ({svc_dir})"
    return test


for _svc, _mod in SERVICE_MODULES:
    _name = f"test_import__{_svc.replace('/', '_')}__{_mod.replace('.', '_')}"
    setattr(TestImportSmoke, _name, _make_import_test(_svc, _mod))


# ===========================================================================
# Category 2: Environment Contract Tests
# ===========================================================================
ENV_CONTRACTS = [
    {
        "service": "ai",
        "plist": Path.home() / "Library/LaunchAgents/com.cftc.ai.plist",
        "env_file": PROJECT_ROOT / "services/ai/.env",
        # Vars with no safe default - MUST be in plist
        "required_vars": [
            "ANTHROPIC_API_KEY",
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USER",
            "SMTP_PASS",
            "BRIEF_RECIPIENT",
            "TRACKER_USER",
            "TRACKER_PASS",
        ],
    },
    {
        "service": "tracker",
        "plist": Path.home() / "Library/LaunchAgents/com.cftc.tracker.plist",
        "env_file": PROJECT_ROOT / "services/tracker/.env",
        "required_vars": [
            "TRACKER_USER",
            "TRACKER_PASS",
            "TRACKER_DB_PATH",
        ],
    },
]


class TestEnvContract(unittest.TestCase):
    """Runtime environment must provide every variable the code requires."""

    def _plist_env_vars(self, plist_path):
        """Extract EnvironmentVariables keys from a launchd plist."""
        if not plist_path.exists():
            self.skipTest(f"Plist not found: {plist_path}")
        with open(plist_path, "rb") as f:
            data = plistlib.load(f)
        return set(data.get("EnvironmentVariables", {}).keys())

    def _dotenv_keys(self, env_path):
        """Extract KEY names from a .env file."""
        if not env_path.exists():
            return set()
        keys = set()
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([A-Z_][A-Z0-9_]*)=", line)
            if match:
                keys.add(match.group(1))
        return keys


# Dynamically generate tests per contract
def _make_required_test(contract):
    def test(self):
        plist_vars = self._plist_env_vars(contract["plist"])
        missing = set(contract["required_vars"]) - plist_vars
        self.assertFalse(
            missing,
            f"Service '{contract['service']}' plist is missing required env vars: "
            f"{sorted(missing)}\n"
            f"Plist: {contract['plist']}",
        )

    test.__doc__ = f"plist has required vars ({contract['service']})"
    return test


def _make_dotenv_test(contract):
    def test(self):
        plist_vars = self._plist_env_vars(contract["plist"])
        dotenv_keys = self._dotenv_keys(contract["env_file"])
        if not dotenv_keys:
            self.skipTest(f"No .env file: {contract['env_file']}")
        # Vars that have safe defaults or are set by the system
        safe_defaults = {
            "PYTHONUNBUFFERED", "PATH", "APP_ENV", "LOCAL_TIMEZONE",
            "SMTP_FROM",  # Falls back to f"CFTC AI <{SMTP_USER}>"
        }
        missing = dotenv_keys - plist_vars - safe_defaults
        self.assertFalse(
            missing,
            f"Service '{contract['service']}' .env has keys missing from plist: "
            f"{sorted(missing)}\n"
            f"Plist: {contract['plist']}\n"
            f".env:  {contract['env_file']}",
        )

    test.__doc__ = f".env keys are in plist ({contract['service']})"
    return test


for _c in ENV_CONTRACTS:
    _svc = _c["service"]
    setattr(TestEnvContract, f"test_required_vars__{_svc}", _make_required_test(_c))
    setattr(TestEnvContract, f"test_dotenv_coverage__{_svc}", _make_dotenv_test(_c))


# ===========================================================================
# Category 3: API Contract Tests
# ===========================================================================
API_CONTRACTS = [
    # --- AI -> Tracker dependencies ---
    {
        "consumer": "ai.jobs.daily_brief",
        "url": "http://127.0.0.1:8004/tracker/system-events",
        "auth": TRACKER_AUTH,
        "params": {"limit": "3"},
        "expected_status": 200,
        "expected_keys": ["items", "total"],
        "item_keys": ["entity_type", "entity_id", "action", "created_at"],
    },
    {
        "consumer": "ai.jobs.daily_brief",
        "url": "http://127.0.0.1:8004/tracker/ai-context/intelligence-data",
        "auth": TRACKER_AUTH,
        "params": {},
        "expected_status": 200,
        "expected_keys": [],
    },
    {
        "consumer": "ai.jobs.daily_brief",
        "url": "http://127.0.0.1:8004/tracker/meetings",
        "auth": TRACKER_AUTH,
        "params": {"limit": "1"},
        "expected_status": 200,
        "expected_keys": ["items"],
    },
    {
        "consumer": "ai.jobs.daily_brief",
        "url": "http://127.0.0.1:8004/tracker/tasks",
        "auth": TRACKER_AUTH,
        "params": {"limit": "1"},
        "expected_status": 200,
        "expected_keys": ["items"],
    },
    {
        "consumer": "ai.jobs.daily_brief",
        "url": "http://127.0.0.1:8004/tracker/people",
        "auth": TRACKER_AUTH,
        "params": {"limit": "1"},
        "expected_status": 200,
        "expected_keys": ["items"],
    },
    {
        "consumer": "ai.jobs.daily_brief",
        "url": "http://127.0.0.1:8004/tracker/matters",
        "auth": TRACKER_AUTH,
        "params": {"limit": "1"},
        "expected_status": 200,
        "expected_keys": ["items"],
    },
    {
        "consumer": "ai.jobs.daily_brief",
        "url": "http://127.0.0.1:8004/tracker/decisions",
        "auth": TRACKER_AUTH,
        "params": {"limit": "1"},
        "expected_status": 200,
        "expected_keys": ["items"],
    },
    {
        "consumer": "ai.jobs.daily_brief",
        "url": "http://127.0.0.1:8004/tracker/policy-directives",
        "auth": TRACKER_AUTH,
        "params": {"limit": "1"},
        "expected_status": 200,
        "expected_keys": ["items"],
    },
    # --- Health checks (public, no auth) ---
    {
        "consumer": "tracker.main",
        "url": "http://127.0.0.1:8006/ai/api/health",
        "auth": None,
        "params": {},
        "expected_status": 200,
        "expected_keys": ["status"],
    },
    {
        "consumer": "ai.main",
        "url": "http://127.0.0.1:8004/tracker/health",
        "auth": None,
        "params": {},
        "expected_status": 200,
        "expected_keys": ["status"],
    },
]


class TestAPIContract(unittest.TestCase):
    """Every cross-service HTTP dependency must be reachable with expected shape."""


def _make_api_test(contract):
    def test(self):
        status, body = _http_get(
            contract["url"],
            params=contract.get("params"),
            auth=contract.get("auth"),
        )
        self.assertEqual(
            status,
            contract.get("expected_status", 200),
            f"Consumer {contract['consumer']} -> {contract['url']}\n"
            f"Expected {contract.get('expected_status', 200)}, got {status}\n"
            f"Body: {str(body)[:300]}",
        )
        if contract.get("expected_keys") and isinstance(body, dict):
            for key in contract["expected_keys"]:
                self.assertIn(
                    key,
                    body,
                    f"Response from {contract['url']} missing key '{key}'\n"
                    f"Consumer: {contract['consumer']}\n"
                    f"Keys present: {sorted(body.keys())}",
                )
        # Validate item shape if specified
        if contract.get("item_keys") and isinstance(body, dict):
            items = body.get("items", [])
            if items:
                first = items[0]
                for key in contract["item_keys"]:
                    self.assertIn(
                        key,
                        first,
                        f"Item from {contract['url']} missing key '{key}'\n"
                        f"Consumer: {contract['consumer']}\n"
                        f"Item keys: {sorted(first.keys())}",
                    )

    path = contract["url"].split("//")[1].split("/", 1)[1] if "//" in contract["url"] else contract["url"]
    test.__doc__ = f"{contract['consumer']} -> /{path}"
    return test


for _i, _c in enumerate(API_CONTRACTS):
    _path = _c["url"].rsplit("/", 1)[-1].replace("-", "_")
    _name = f"test_contract__{_c['consumer'].replace('.', '_')}__{_path}"
    if hasattr(TestAPIContract, _name):
        _name += f"_{_i}"
    setattr(TestAPIContract, _name, _make_api_test(_c))


# ===========================================================================
# Category 4: Operational Health Tests
# ===========================================================================
LOG_LIMITS = [
    # (path, max_bytes, description)
    ("/tmp/cftc-caddy.log", 50_000_000, "Caddy reverse proxy"),
    ("/tmp/cftc-ai.log", 50_000_000, "AI service"),
    ("/tmp/cftc-tracker.log", 10_000_000, "Tracker service"),
    ("/tmp/cftctools-backend.log", 10_000_000, "CFTC Tools backend"),
    ("/tmp/sauron.log", 10_000_000, "Sauron API"),
]

HEALTH_ENDPOINTS = [
    ("tracker", "http://127.0.0.1:8004/tracker/health"),
    ("ai", "http://127.0.0.1:8006/ai/api/health"),
]

MIN_DISK_FREE_MB = 5_000  # 5 GB


class TestOpsHealth(unittest.TestCase):
    """Operational health: logs bounded, disk OK, services alive."""

    def test_log_rotation_configured(self):
        """Crontab contains log rotation job."""
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=5
        )
        self.assertIn(
            "rotate-logs",
            result.stdout,
            "No log rotation cron job found. Run:\n"
            "  (crontab -l; echo '5 3 * * * .../rotate-logs.sh') | crontab -",
        )

    def test_disk_space(self):
        """Free disk space above minimum threshold."""
        stat = shutil.disk_usage("/")
        free_mb = stat.free // (1024 * 1024)
        self.assertGreater(
            free_mb,
            MIN_DISK_FREE_MB,
            f"Low disk space: {free_mb} MB free (threshold: {MIN_DISK_FREE_MB} MB)",
        )


def _make_log_size_test(path, max_bytes, desc):
    def test(self):
        p = Path(path)
        if not p.exists():
            return  # Log file not present = not a problem
        size = p.stat().st_size
        self.assertLess(
            size,
            max_bytes,
            f"{desc} log is {size / 1_000_000:.1f} MB "
            f"(limit: {max_bytes / 1_000_000:.0f} MB)\n"
            f"File: {path}",
        )

    test.__doc__ = f"log size: {desc} < {max_bytes // 1_000_000}MB"
    return test


def _make_service_alive_test(name, url):
    def test(self):
        status, body = _http_get(url, timeout=5)
        self.assertEqual(
            status,
            200,
            f"Service '{name}' not responding at {url} (status={status})",
        )
        if isinstance(body, dict):
            self.assertEqual(
                body.get("status"), "ok", f"Service '{name}' unhealthy: {body}"
            )

    test.__doc__ = f"service alive: {name}"
    return test


for _path, _max, _desc in LOG_LIMITS:
    _name = f"test_log_size__{Path(_path).stem.replace('-', '_')}"
    setattr(TestOpsHealth, _name, _make_log_size_test(_path, _max, _desc))

for _svc_name, _url in HEALTH_ENDPOINTS:
    setattr(
        TestOpsHealth,
        f"test_service_alive__{_svc_name}",
        _make_service_alive_test(_svc_name, _url),
    )


# ===========================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Application configuration."""

import json
import os
import sys
from pathlib import Path


class Settings:
    def __init__(self):
        self.APP_ENV = os.environ.get("APP_ENV", "development")
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
        self.CORS_ORIGINS = os.environ.get("CORS_ORIGINS", '["http://localhost:3000"]')
        self.COMMENTS_DB_PATH = Path(os.environ.get(
            "COMMENTS_DB_PATH",
            str(Path(__file__).parent.parent.parent / "data" / "comments.db")
        ))
        self.REGULATIONS_GOV_BASE_URL = "https://api.regulations.gov/v4"
        self.FEDERAL_REGISTER_BASE_URL = "https://www.federalregister.gov/api/v1"

        # ── Sensitive settings: empty defaults, fail closed in production ──
        self.SECRET_KEY = os.environ.get("SECRET_KEY", "")
        self.ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
        self.REGULATIONS_GOV_API_KEY = os.environ.get("REGULATIONS_GOV_API_KEY", "")

        # Auth credentials for pipeline routes
        self.PIPELINE_USER = os.environ.get("PIPELINE_USER", "")
        self.PIPELINE_PASS = os.environ.get("PIPELINE_PASS", "")

        # Fail closed: require SECRET_KEY in production
        if self.APP_ENV == "production" and not self.SECRET_KEY:
            print("FATAL: SECRET_KEY env var is required in production", file=sys.stderr)
            sys.exit(1)

        # Fail closed: require pipeline auth in production
        if self.APP_ENV == "production" and (not self.PIPELINE_USER or not self.PIPELINE_PASS):
            print("FATAL: PIPELINE_USER and PIPELINE_PASS env vars are required in production", file=sys.stderr)
            sys.exit(1)

    @property
    def cors_origins_list(self):
        return json.loads(self.CORS_ORIGINS)


settings = Settings()

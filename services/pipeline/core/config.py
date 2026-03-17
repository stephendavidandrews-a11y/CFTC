"""Pipeline application configuration."""

import json
import os
import sys


class Settings:
    def __init__(self):
        self.APP_ENV = os.environ.get("APP_ENV", "development")
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
        self.CORS_ORIGINS = os.environ.get("CORS_ORIGINS", '["http://localhost:3000"]')

        # Sensitive settings
        self.SECRET_KEY = os.environ.get("SECRET_KEY", "")
        self.ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

        # Auth credentials
        self.PIPELINE_USER = os.environ.get("PIPELINE_USER", "")
        self.PIPELINE_PASS = os.environ.get("PIPELINE_PASS", "")

        # Fail closed in production
        if self.APP_ENV == "production" and not self.SECRET_KEY:
            print("FATAL: SECRET_KEY env var is required in production", file=sys.stderr)
            sys.exit(1)
        if self.APP_ENV == "production" and (not self.PIPELINE_USER or not self.PIPELINE_PASS):
            print("FATAL: PIPELINE_USER and PIPELINE_PASS required in production", file=sys.stderr)
            sys.exit(1)

    @property
    def cors_origins_list(self):
        return json.loads(self.CORS_ORIGINS)


settings = Settings()

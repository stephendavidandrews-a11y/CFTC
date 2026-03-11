"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cftc_user:changeme@localhost:5432/cftc_comments"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://cftc_user:changeme@localhost:5432/cftc_comments"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # APIs
    REGULATIONS_GOV_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # S3
    S3_BUCKET_NAME: str = "cftc-comment-pdfs"
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str | None = None
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # Auth
    SECRET_KEY: str = "dev-secret-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = '["http://localhost:3000"]'

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

    # API base URLs (constants)
    REGULATIONS_GOV_BASE_URL: str = "https://api.regulations.gov/v4"
    FEDERAL_REGISTER_BASE_URL: str = "https://www.federalregister.gov/api/v1"

    # Rate limiting
    REGULATIONS_GOV_RATE_LIMIT: int = 1000  # per hour
    FEDERAL_REGISTER_RATE_LIMIT: int = 1000  # per hour

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

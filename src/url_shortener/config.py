"""Configuration, read from environment variables only.

See https://12factor.net/config. Nothing environment-specific belongs in
code: each deploy (local, CI, staging, production) supplies its own values.
For local development, copy `.env.example` to `.env`.
"""

import logging
import sys
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    access_log: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


def configure_logging():
    """Write logs as an unbuffered event stream to stdout (https://12factor.net/logs)."""
    logging.basicConfig(
        stream=sys.stdout,
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )

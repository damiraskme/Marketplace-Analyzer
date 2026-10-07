from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    kafka_bootstrap_servers: str
    kafka_topic_readings: str
    kafka_topic_changes: str
    kafka_topic_alerts: str

    redis_url: str
    collect_lock_ttl_seconds: int
    alert_cooldown_seconds: int
    rate_limit_per_minute: int

    oracle_user: str
    oracle_password: str
    oracle_dsn: str

    marketplace: str
    fake_marketplace_url: str
    fake_change_interval_seconds: int = 10
    collect_interval_seconds: int

    telegram_bot_token: str = ""

    api_base_url: str
    session_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

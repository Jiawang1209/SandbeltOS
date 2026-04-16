from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://sandbelt:sandbelt@localhost:5432/sandbelt_db"
    database_url_sync: str = "postgresql://sandbelt:sandbelt@localhost:5432/sandbelt_db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"

    # GEE
    gee_project: str = "ee-yueliu19921209"
    gee_service_account: str = ""
    gee_key_file: str = "secrets/gee-key.json"

    # CDS API
    cds_url: str = "https://cds.climate.copernicus.eu/api/v2"
    cds_key: str = ""

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()

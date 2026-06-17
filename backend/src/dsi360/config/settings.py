"""Configuration applicative — chargée de l'environnement, jamais de secret en dur (cf. SECURITY)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DSI360_", env_file=None)

    environnement: Literal["dev", "recette", "prod"] = "dev"
    # DSN PostgreSQL (asyncpg). Fournie par l'environnement / docker-compose.
    database_url: str = "postgresql+asyncpg://dsi360:dsi360@postgres:5432/dsi360"
    redis_url: str = "redis://redis:6379/0"

    # Authentification : LOCAL (dev/bootstrap) | OIDC (Microsoft Entra ID) | LDAP.
    auth_mode: Literal["local", "oidc", "ldap"] = "local"
    jwt_secret_key: str = "changez-moi-en-dev-uniquement"
    jwt_acces_minutes: int = 15

    max_upload_mb: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()

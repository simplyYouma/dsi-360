"""Configuration applicative, chargée de l'environnement (jamais de secret en dur)."""

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
    # Dossier des migrations SQL (monté dans le conteneur api sous /db).
    migrations_dir: str = "/db/migrations"

    # Compte administrateur initial (seed). Mot de passe à changer à la 1re connexion.
    seed_admin_email: str = "admin@afgbank.ml"
    seed_admin_password: str = "changez-moi"


@lru_cache
def get_settings() -> Settings:
    return Settings()

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
    # Dossier des migrations SQL. En natif, fourni par l'environnement (infra/local/env.ps1).
    migrations_dir: str = "/db/migrations"

    # Service du frontend par l'API (prod native, sans reverse-proxy statique).
    # En dev on laisse Vite servir la SPA → garder False.
    servir_frontend: bool = False
    # Chemin du build (frontend/dist). Vide = résolu par rapport au dépôt.
    frontend_dist: str = ""

    # Compte administrateur initial (seed). Mot de passe à changer à la 1re connexion.
    seed_admin_email: str = "admin@afgbank.ml"
    seed_admin_password: str = "changez-moi"

    # Domaines e-mail autorisés pour les comptes (séparés par des virgules). Vide = aucun contrôle.
    domaines_email_autorises: str = "afgbank.ml"
    # URL publique de l'application (liens dans les e-mails : connexion, réinitialisation).
    url_app: str = "https://localhost:8453"
    # Durée de validité d'un lien de réinitialisation de mot de passe (minutes).
    reset_validite_minutes: int = 30

    @property
    def domaines_email(self) -> list[str]:
        return [d.strip().lower() for d in self.domaines_email_autorises.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

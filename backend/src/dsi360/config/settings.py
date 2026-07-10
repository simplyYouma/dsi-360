"""Configuration applicative, chargée de l'environnement (jamais de secret en dur)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DSI360_", env_file=None)

    environnement: Literal["dev", "recette", "prod"] = "dev"
    # DSN PostgreSQL (asyncpg). Fournie par l'environnement (exécution native, cf. ADR-0002).
    database_url: str = "postgresql+asyncpg://dsi360:dsi360@postgres:5432/dsi360"

    # Authentification locale : chaque agent définit son mot de passe via le lien d'activation reçu
    # par e-mail (ADR-0004). Pas d'annuaire AD/LDAP/M365 — la colonne core.utilisateur.source_auth
    # garde la porte ouverte, sans prétendre que la plomberie existe.
    jwt_secret_key: str = "changez-moi-en-dev-uniquement"
    jwt_acces_minutes: int = 15

    # Frein sur les tentatives de connexion. Le verrou est temporaire : définitif, il donnerait à un
    # attaquant le pouvoir d'exclure n'importe quel agent en se trompant exprès à sa place.
    login_echecs_max: int = 5
    login_verrou_minutes: int = 15

    max_upload_mb: int = 20
    # Applique les migrations SQL en attente au démarrage de l'API (idempotent). Désactivable en
    # prod si l'on préfère un déploiement manuel des migrations.
    migrer_au_demarrage: bool = True
    # Ordonnanceur natif : intervalle du scan SLA/escalade (secondes). 0 = désactivé.
    sla_scan_intervalle_s: int = 300
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
    # Durée de validité du lien d'activation envoyé à la création d'un compte (minutes) — 1 heure.
    activation_validite_minutes: int = 60

    @property
    def domaines_email(self) -> list[str]:
        return [d.strip().lower() for d in self.domaines_email_autorises.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

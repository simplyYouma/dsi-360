"""Configuration applicative, chargée de l'environnement (jamais de secret en dur)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Valeurs d'usine des secrets : tolérées en dev, refusées au démarrage hors dev (fail-closed).
_DEFAUT_JWT = "changez-moi-en-dev-uniquement"
_DEFAUT_ADMIN_MDP = "changez-moi"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DSI360_", env_file=None)

    environnement: Literal["dev", "recette", "prod"] = "dev"
    # DSN PostgreSQL (asyncpg). Fournie par l'environnement (natif, hôte local — ADR-0002).
    database_url: str = "postgresql+asyncpg://dsi360:dsi360@127.0.0.1:5432/dsi360"

    # Authentification locale : chaque agent définit son mot de passe via le lien d'activation reçu
    # par e-mail (ADR-0004). Pas d'annuaire AD/LDAP/M365 — la colonne core.utilisateur.source_auth
    # garde la porte ouverte, sans prétendre que la plomberie existe.
    jwt_secret_key: str = _DEFAUT_JWT
    jwt_acces_minutes: int = 15

    # Frein sur les tentatives de connexion. Le verrou est temporaire : définitif, il donnerait à un
    # attaquant le pouvoir d'exclure n'importe quel agent en se trompant exprès à sa place.
    login_echecs_max: int = 5
    login_verrou_minutes: int = 15

    # E-mails automatiques (notifications d'activité, échéances SLA). Coupés par défaut (« en
    # veille ») : on les active explicitement quand un relais SMTP est fourni. Les e-mails de compte
    # (activation, réinitialisation) ne sont pas concernés : sans eux, personne n'entre.
    notif_email_active: bool = False
    # Garde-fou : hors production, aucun e-mail ne part réellement, même avec un relais SMTP
    # configuré. Un jeu de démonstration crée des centaines d'assignations — autant d'e-mails vers
    # de vraies boîtes. Mettre à `true` le temps de vérifier le relais de bout en bout.
    email_reel_hors_prod: bool = False

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
    seed_admin_password: str = _DEFAUT_ADMIN_MDP

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

    def secrets_par_defaut(self) -> list[str]:
        """Secrets restés à leur valeur d'usine — connus publiquement, donc interdits hors dev.

        Un secret JWT par défaut rend les jetons forgeables ; un mot de passe admin par défaut
        ouvre le compte administrateur. On refuse de démarrer avec, hors dev (cf. app.creer_app).
        """
        faibles = []
        if self.jwt_secret_key == _DEFAUT_JWT:
            faibles.append("DSI360_JWT_SECRET_KEY")
        if self.seed_admin_password == _DEFAUT_ADMIN_MDP:
            faibles.append("DSI360_SEED_ADMIN_PASSWORD")
        return faibles


@lru_cache
def get_settings() -> Settings:
    return Settings()

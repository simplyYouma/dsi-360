"""Point d'entrée de l'API DSI 360 (FastAPI) : middleware de sécurité, sondes de santé, service
de la SPA compilée, et les routeurs métier montés sous /api/v1.

Architecture en couches : cf. docs/01. Sécurité (en-têtes, CSP, garde des secrets) : cf. docs/04.
"""

import asyncio
import contextlib
import logging
import mimetypes
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import InterfaceError, OperationalError

from dsi360.application.notifications import scanner_tout
from dsi360.config import Settings, get_settings
from dsi360.infrastructure.audit import definir_adresse_ip
from dsi360.infrastructure.db import get_engine
from dsi360.infrastructure.db.migrate import appliquer as appliquer_migrations
from dsi360.interface.routeurs import (
    administration,
    analyses,
    apercu,
    audit_reco,
    auth,
    campagnes,
    changements,
    commentaires,
    cybersecurite,
    demandes,
    demandeurs,
    gouvernance,
    incidents,
    ingestion,
    inventaire,
    mes_tickets,
    notifications,
    projets,
    recherche,
    referentiels,
    risques,
    tableau_de_bord,
)

# Force les types MIME servis en prod. Sur Windows, mimetypes lit le registre : `.js` y est parfois
# `text/plain`, ce qui — avec l'en-tête nosniff — fait REFUSER le bundle et le service worker par le
# navigateur (page blanche). On fige les valeurs correctes pour que le build charge sur n'importe
# quel serveur, quel que soit son registre.
for _type, _ext in (
    ("text/javascript", ".js"),
    ("text/javascript", ".mjs"),
    ("text/css", ".css"),
    ("application/manifest+json", ".webmanifest"),
    ("image/svg+xml", ".svg"),
):
    mimetypes.add_type(_type, _ext)

_log = logging.getLogger("dsi360.ordonnanceur")


async def _ordonnanceur(intervalle_s: int) -> None:
    """Tâche de fond native : rappels d'échéance (SLA, tâches, jalons, projets, revues) + escalades.

    Remplace le worker/beat Celery (exécution native sans Redis, cf. ADR-0002).
    """
    while True:
        await asyncio.sleep(intervalle_s)
        try:
            await scanner_tout()
        except Exception as exc:  # noqa: BLE001 — un scan raté ne doit pas tuer la boucle
            _log.warning("Scan des échéances / escalades échec : %s", exc)


@contextlib.asynccontextmanager
async def _cycle_vie(app: FastAPI) -> AsyncIterator[None]:
    # Applique les migrations en attente au démarrage : la base reste toujours en phase avec le
    # code (plus besoin de lancer `migrate` à la main après un `git pull`). Idempotent + verrouillé.
    if get_settings().migrer_au_demarrage:
        try:
            n = await appliquer_migrations(silencieux=True)
            if n:
                _log.info("Migrations appliquées au démarrage : %d", n)
        except Exception as exc:  # noqa: BLE001 — on journalise, l'échec se voit aussi aux requêtes
            _log.error("Échec des migrations au démarrage : %s", exc)
    intervalle = get_settings().sla_scan_intervalle_s
    tache = asyncio.create_task(_ordonnanceur(intervalle)) if intervalle > 0 else None
    try:
        yield
    finally:
        if tache is not None:
            tache.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tache


async def _capter_ip(request: Request) -> None:
    """Dépendance globale : mémorise l'IP de la requête pour l'audit (même contexte)."""
    definir_adresse_ip(request.client.host if request.client else None)


def _monter_frontend(app: FastAPI, settings: Settings) -> None:
    """Sert la SPA (build Vite) directement depuis l'API — prod native sans reverse-proxy statique.

    Les routes /api/*, /healthz, /readyz sont enregistrées avant : elles gardent la priorité.
    Le catch-all renvoie le fichier demandé s'il existe, sinon index.html (routage SPA côté client).
    """
    defaut = Path(__file__).resolve().parents[4] / "frontend" / "dist"
    dist = Path(settings.frontend_dist) if settings.frontend_dist else defaut
    if not dist.is_dir():
        return
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{chemin:path}", include_in_schema=False)
    async def spa(chemin: str) -> FileResponse:
        cible = dist / chemin
        if chemin and cible.is_file():
            return FileResponse(cible)
        return FileResponse(dist / "index.html")


def creer_app() -> FastAPI:
    settings = get_settings()
    # Fail-closed : hors dev, on refuse de démarrer avec un secret d'usine (jeton forgeable, compte
    # admin ouvert). Mieux vaut un démarrage bruyant qu'une prod silencieusement vulnérable.
    if settings.environnement != "dev":
        faibles = settings.secrets_par_defaut()
        if faibles:
            raise RuntimeError(
                f"Démarrage refusé en {settings.environnement} : secret(s) laissé(s) par défaut — "
                f"{', '.join(faibles)}. Renseignez-les dans l'environnement avant de démarrer."
            )
    app = FastAPI(
        title="DSI 360 — API",
        version="0.1.0",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        lifespan=_cycle_vie,
    )

    @app.middleware("http")
    async def _entetes_securite(request: Request, appel):  # type: ignore[no-untyped-def]
        """En-têtes de sécurité sur chaque réponse : défense en profondeur, gratuite et globale."""
        reponse = await appel(request)
        reponse.headers["X-Content-Type-Options"] = "nosniff"
        reponse.headers["X-Frame-Options"] = "DENY"
        reponse.headers["Referrer-Policy"] = "no-referrer"
        reponse.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # CSP : l'app est mono-origine (l'API sert la SPA). Tout vient de 'self' ; aucune source
        # externe (le carillon de notif est synthétisé, pas un fichier). 'unsafe-inline' sur les
        # styles couvre les `style=` de la charte ; les scripts, eux, restent stricts ('self').
        reponse.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; "
            "img-src 'self' data:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; form-action 'self'"
        )
        # HSTS seulement hors dev (là où le TLS est présent : uvicorn --ssl ou reverse-proxy).
        if settings.environnement != "dev":
            reponse.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return reponse

    @app.exception_handler(OperationalError)
    @app.exception_handler(InterfaceError)
    async def _base_indisponible(request: Request, exc: Exception) -> JSONResponse:
        """La base ne répond pas : on rend un 503 propre plutôt qu'un 500 qui fuit des détails.

        Le serveur de la banque tombe souvent ; l'app ne doit pas tomber avec lui — elle refuse
        proprement, se rétablit dès que la base revient (pool_pre_ping), et ne divulgue rien.
        """
        _log.error("Base indisponible : %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"detail": "Service momentanément indisponible. Réessayez dans un instant."},
        )

    @app.get("/healthz", tags=["sante"], summary="Vivant")
    def healthz() -> dict[str, str]:
        return {"statut": "ok", "environnement": settings.environnement}

    @app.get("/readyz", tags=["sante"], summary="Prêt")
    async def readyz() -> dict[str, str]:
        # Vérifie que la base répond (ping SELECT 1).
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            db = "ok"
        except Exception:  # noqa: BLE001 — sonde : on rapporte l'état, on ne propage pas.
            db = "ko"
        return {"statut": "pret" if db == "ok" else "degrade", "db": db}

    v1 = APIRouter(prefix="/api/v1", dependencies=[Depends(_capter_ip)])
    v1.include_router(auth.routeur)
    v1.include_router(administration.routeur)
    v1.include_router(referentiels.routeur)
    v1.include_router(notifications.routeur)
    v1.include_router(tableau_de_bord.routeur)
    v1.include_router(analyses.routeur)
    v1.include_router(apercu.routeur)
    v1.include_router(recherche.routeur)
    v1.include_router(ingestion.routeur)
    v1.include_router(demandeurs.routeur)
    v1.include_router(commentaires.routeur)
    v1.include_router(mes_tickets.routeur)
    v1.include_router(incidents.routeur)
    v1.include_router(demandes.routeur)
    v1.include_router(changements.routeur)
    v1.include_router(audit_reco.routeur)
    v1.include_router(risques.routeur)
    v1.include_router(cybersecurite.routeur)
    v1.include_router(gouvernance.routeur)
    v1.include_router(projets.routeur)
    # Avant `inventaire` : sinon /inventaire/{ident} avalerait /inventaire/campagnes.
    v1.include_router(campagnes.routeur)
    v1.include_router(inventaire.routeur)
    app.include_router(v1)
    if settings.servir_frontend:
        _monter_frontend(app, settings)
    return app


app = creer_app()

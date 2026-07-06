"""Point d'entrée de l'API DSI 360 (FastAPI). Pour l'instant : sondes de santé + squelette v1.

Les routeurs des modules (incidents, demandes, projets, dashboard…) seront montés sous /api/v1
au fur et à mesure des lots (cf. docs/07-ROADMAP.md). Architecture en couches : cf. docs/01.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from dsi360.application.notifications import scanner_tout
from dsi360.config import Settings, get_settings
from dsi360.infrastructure.db import get_engine
from dsi360.interface.routeurs import (
    administration,
    analyses,
    audit_reco,
    auth,
    changements,
    commentaires,
    cybersecurite,
    demandes,
    demandeurs,
    gouvernance,
    incidents,
    ingestion,
    mes_tickets,
    notifications,
    projets,
    recherche,
    referentiels,
    risques,
    tableau_de_bord,
)

_log = logging.getLogger("dsi360.ordonnanceur")


async def _ordonnanceur(intervalle_s: int) -> None:
    """Tâche de fond native : scanne périodiquement les échéances SLA et les escalades P1.

    Remplace le worker/beat Celery (exécution native sans Redis, cf. ADR-0002).
    """
    while True:
        await asyncio.sleep(intervalle_s)
        try:
            await scanner_tout()
        except Exception as exc:  # noqa: BLE001 — un scan raté ne doit pas tuer la boucle
            _log.warning("Scan SLA/escalade échec : %s", exc)


@contextlib.asynccontextmanager
async def _cycle_vie(app: FastAPI) -> AsyncIterator[None]:
    intervalle = get_settings().sla_scan_intervalle_s
    tache = asyncio.create_task(_ordonnanceur(intervalle)) if intervalle > 0 else None
    try:
        yield
    finally:
        if tache is not None:
            tache.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tache


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
    app = FastAPI(
        title="DSI 360 — API",
        version="0.1.0",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        lifespan=_cycle_vie,
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

    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(auth.routeur)
    v1.include_router(administration.routeur)
    v1.include_router(referentiels.routeur)
    v1.include_router(notifications.routeur)
    v1.include_router(tableau_de_bord.routeur)
    v1.include_router(analyses.routeur)
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
    app.include_router(v1)
    if settings.servir_frontend:
        _monter_frontend(app, settings)
    return app


app = creer_app()

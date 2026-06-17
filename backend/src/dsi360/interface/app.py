"""Point d'entrée de l'API DSI 360 (FastAPI). Pour l'instant : sondes de santé + squelette v1.

Les routeurs des modules (incidents, demandes, projets, dashboard…) seront montés sous /api/v1
au fur et à mesure des lots (cf. docs/07-ROADMAP.md). Architecture en couches : cf. docs/01.
"""

from fastapi import APIRouter, FastAPI
from sqlalchemy import text

from dsi360.config import get_settings
from dsi360.infrastructure.db import get_engine


def creer_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DSI 360 — API",
        version="0.1.0",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
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
    # v1.include_router(incidents.routeur) … (lots à venir)
    app.include_router(v1)
    return app


app = creer_app()

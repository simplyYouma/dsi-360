"""Ingestion du rapport quotidien de tickets (.xlsx) -> Incidents + Demandes.

Réservé aux profils transverses (ADMIN / DSI / DG). Idempotent : recharger met à jour.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.ingestion import importer_tickets
from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import RapportImport
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/import", tags=["ingestion"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]

_MAX = 20 * 1024 * 1024  # 20 Mo


def _exiger_transverse(courant: dict[str, Any]) -> None:
    if not courant["transverse"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Import réservé aux profils transverses (DSI / Administration).",
        )


@routeur.post("/tickets", response_model=RapportImport)
async def importer(fichier: UploadFile, courant: Courant, session: Session) -> dict[str, Any]:
    _exiger_transverse(courant)
    contenu = await fichier.read()
    if len(contenu) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier vide.")
    if len(contenu) > _MAX:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fichier trop volumineux.",
        )
    try:
        return await importer_tickets(session, contenu, courant)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

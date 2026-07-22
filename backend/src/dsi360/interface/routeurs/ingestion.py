"""Imports de fichiers : rapport quotidien de tickets, et inventaire des équipements.

Réservés aux profils transverses (ADMIN / DSI / DG). Idempotents : recharger met à jour, sans
jamais créer de doublon — par n° de ticket pour l'un, par code d'immobilisation pour l'autre.
"""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.import_equipements import importer_classeur
from dsi360.application.ingestion import importer_tickets
from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import EtatImports, RapportImport, RapportImportEquipements
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/import", tags=["ingestion"])

# Le journal d'audit consigne chaque import (action IMPORT) avec son compte-rendu : c'est lui la
# mémoire des dépôts — aucune table dédiée à entretenir. cible_type distingue les natures.
_DERNIERS_IMPORTS = """
SELECT DISTINCT ON (j.cible_type)
       j.cible_type, j.horodatage, j.acteur_email, j.nouvelle_valeur
FROM audit.journal j
WHERE j.action = 'IMPORT' AND j.cible_type IN ('rapport_tickets', 'equipement')
ORDER BY j.cible_type, j.id DESC
"""

_NATURE = {"rapport_tickets": "tickets", "equipement": "equipements"}
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


def _lire(contenu: bytes) -> None:
    """Contrôles communs à tout dépôt de fichier."""
    if len(contenu) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier vide.")
    if len(contenu) > _MAX:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fichier trop volumineux.",
        )


@routeur.post("/equipements", response_model=RapportImportEquipements)
async def importer_equipements(
    fichier: UploadFile, courant: Courant, session: Session
) -> dict[str, Any]:
    """Inventaire des immobilisations IT. Ne remplace jamais ce que la DSI a saisi à l'écran."""
    _exiger_transverse(courant)
    contenu = await fichier.read()
    _lire(contenu)
    try:
        return await importer_classeur(session, contenu, courant)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@routeur.get("/etat", response_model=EtatImports)
async def etat(courant: Courant, session: Session) -> dict[str, Any]:
    """Dernier import de chaque nature : on sait d'un coup d'œil si le dépôt du jour est fait."""
    _exiger_transverse(courant)
    lignes = (await session.execute(text(_DERNIERS_IMPORTS))).mappings().all()
    derniers = []
    for r in lignes:
        brut = r["nouvelle_valeur"]
        if isinstance(brut, str):
            brut = json.loads(brut)
        details = {k: v for k, v in (brut or {}).items() if isinstance(v, int)}
        derniers.append(
            {
                "nature": _NATURE.get(r["cible_type"], r["cible_type"]),
                "horodatage": r["horodatage"],
                "acteur": r["acteur_email"],
                "details": details,
            }
        )
    return {"derniers": derniers}

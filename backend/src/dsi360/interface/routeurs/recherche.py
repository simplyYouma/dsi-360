"""Recherche globale : référence ou titre d'activité, cloisonnée par accès et par direction.

Légère (ILIKE indexé, 12 résultats max) mais pertinente : ne renvoie que les modules
auxquels l'utilisateur a accès et, hors profils transverses, sa seule direction.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import ResultatRecherche
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/recherche", tags=["recherche"])

Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]

# Module domaine -> clé d'accès RBAC (pluriel utilisé dans core.acces_role).
ACCES_MODULE = {
    "incident": "incidents",
    "demande": "demandes",
    "projet": "projets",
    "changement": "changements",
    "audit": "audit",
    "risque": "risques",
    "cybersecurite": "cybersecurite",
    "gouvernance": "gouvernance",
}

_REQUETE = (
    text(
        "SELECT a.module, a.id::text AS id, a.reference, a.titre, a.statut "
        "FROM core.activite a "
        "LEFT JOIN core.direction d ON d.id = a.direction_id "
        "WHERE a.module IN :modules "
        "AND (a.reference ILIKE :q OR a.titre ILIKE :q) "
        "AND (:tous OR d.code IS NULL OR d.code = :direction) "
        "ORDER BY a.cree_le DESC LIMIT 12"
    )
    .bindparams(bindparam("modules", expanding=True))
)


@routeur.get("", response_model=list[ResultatRecherche])
async def rechercher(
    courant: Courant,
    session: Session,
    q: Annotated[str, Query(min_length=1, max_length=80)],
) -> list[dict[str, Any]]:
    modules = [m for m, cle in ACCES_MODULE.items() if cle in courant["acces"]]
    if not modules:
        return []
    lignes = await session.execute(
        _REQUETE,
        {
            "modules": modules,
            "q": f"%{q.strip()}%",
            "tous": bool(courant["transverse"]),
            "direction": courant["direction"],
        },
    )
    return [dict(x) for x in lignes.mappings().all()]

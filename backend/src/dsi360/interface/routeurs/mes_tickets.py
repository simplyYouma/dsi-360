"""File de travail de l'agent DSI connecté : tickets (incidents/demandes…) qui lui sont assignés.

Vue temps réel « je me connecte et je vois ce que je dois traiter », triée par priorité puis
échéance SLA. Les éléments clôturés en sont exclus.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.sla import statut_sla
from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import MonTicket
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/mes-tickets", tags=["mes-tickets"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]
_FENETRE = timedelta(hours=2)

_REQUETE = text(
    "SELECT a.module, a.id::text AS id, a.reference, a.titre, a.statut, a.priorite, "
    "a.sla_resolution_le, a.cree_le, dem.nom_complet AS demandeur, "
    "(SELECT count(*) FROM core.commentaire cm WHERE cm.activite_id = a.id) AS nb_commentaires "
    "FROM core.activite a LEFT JOIN core.demandeur dem ON dem.id = a.demandeur_externe_id "
    "WHERE a.responsable_id = cast(:id as uuid) AND a.cloture_le IS NULL "
    "AND a.module IN ('incident','demande','changement','audit','cybersecurite','gouvernance') "
    "ORDER BY a.priorite NULLS LAST, a.sla_resolution_le NULLS LAST LIMIT 200"
)


@routeur.get("", response_model=list[MonTicket])
async def mes_tickets(courant: Courant, session: Session) -> list[dict[str, Any]]:
    lignes = (await session.execute(_REQUETE, {"id": courant["id"]})).mappings().all()
    maintenant = datetime.now(UTC)
    resultat: list[dict[str, Any]] = []
    for r in lignes:
        echeance = r["sla_resolution_le"]
        etat = statut_sla(echeance, maintenant, _FENETRE) if echeance is not None else "a_lheure"
        resultat.append({**dict(r), "statut_sla": etat})
    return resultat

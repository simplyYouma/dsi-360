"""Cas d'usage des projets : création (champs propres en `donnees`) et avancement."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.etats import etat_initial
from dsi360.infrastructure import audit
from dsi360.infrastructure.repositories import activite as repo

MODULE = "projet"


async def creer_projet(
    session: AsyncSession,
    *,
    titre: str,
    description: str | None,
    direction_id: str | None,
    responsable_id: str | None,
    sponsor: str | None,
    budget: float | None,
    date_debut: str | None,
    date_fin: str | None,
    acteur: dict[str, Any],
) -> str:
    debut = datetime.now(UTC)
    reference = await repo.prochaine_reference(session, MODULE, debut.year)
    statut = etat_initial(MODULE)
    donnees = {
        "sponsor": sponsor,
        "budget": budget,
        "date_debut": date_debut,
        "date_fin": date_fin,
        "avancement": 0,
    }
    identifiant = await repo.creer(
        session,
        {
            "reference": reference,
            "module": MODULE,
            "titre": titre,
            "description": description,
            "direction_id": direction_id,
            "demandeur_id": acteur["id"],
            "responsable_id": responsable_id,
            "statut": statut,
            "donnees": json.dumps(donnees),
        },
    )
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=MODULE,
        cible_type=MODULE,
        cible_id=reference,
        nouvelle={"reference": reference, "titre": titre, "statut": statut},
    )
    return identifiant


async def maj_avancement(
    session: AsyncSession, identifiant: str, avancement: int, acteur: dict[str, Any]
) -> None:
    await repo.maj_donnees(session, identifiant, {"avancement": avancement})
    await audit.consigner(
        session,
        action="AVANCEMENT",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=MODULE,
        cible_type=MODULE,
        cible_id=identifiant,
        nouvelle={"avancement": avancement},
    )

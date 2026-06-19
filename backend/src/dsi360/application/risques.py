"""Cas d'usage des risques IT : création (criticité = probabilité × impact)."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.activite import calculer_criticite
from dsi360.domain.etats import etat_initial
from dsi360.domain.texte import phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.repositories import activite as repo

MODULE = "risque"


async def creer_risque(
    session: AsyncSession,
    *,
    titre: str,
    description: str | None,
    direction_id: str | None,
    responsable_id: str | None,
    probabilite: int,
    impact: int,
    acteur: dict[str, Any],
) -> str:
    debut = datetime.now(UTC)
    criticite = calculer_criticite(probabilite, impact)
    reference = await repo.prochaine_reference(session, MODULE, debut.year)
    statut = etat_initial(MODULE)
    donnees = {"probabilite": probabilite, "impact": impact, "criticite": criticite}
    identifiant = await repo.creer(
        session,
        {
            "reference": reference,
            "module": MODULE,
            "titre": phrase_propre(titre),
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
        nouvelle={"reference": reference, "titre": titre, "criticite": criticite},
    )
    return identifiant

"""Cas d'usage des projets : création, édition du cadrage (colonnes + `donnees`)."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.etats import etat_initial
from dsi360.domain.texte import nom_propre, phrase_propre
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
        "sponsor": nom_propre(sponsor),
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
        nouvelle={"reference": reference, "titre": titre, "statut": statut},
    )
    return identifiant


# Champs stockés en colonnes (core.activite) vs dans le JSON `donnees`.
_COLONNES_MAJ = {"titre", "description", "responsable_id"}
_DONNEES_MAJ = {"sponsor", "budget", "date_debut", "date_fin"}


async def maj_projet(
    session: AsyncSession, identifiant: str, champs: dict[str, Any], acteur: dict[str, Any]
) -> None:
    """Modifie le cadrage d'un projet (édition en place depuis la fiche)."""
    colonnes = {c: v for c, v in champs.items() if c in _COLONNES_MAJ}
    if "titre" in colonnes and colonnes["titre"] is not None:
        colonnes["titre"] = phrase_propre(colonnes["titre"])
    if colonnes:
        fragments = []
        for c in colonnes:
            fragments.append(
                f"{c} = cast(:{c} as uuid)" if c == "responsable_id" else f"{c} = :{c}"
            )
        await session.execute(
            text(f"UPDATE core.activite SET {', '.join(fragments)} WHERE id::text = :id"),
            {"id": identifiant, **colonnes},
        )
    fragment_json = {c: v for c, v in champs.items() if c in _DONNEES_MAJ}
    if "sponsor" in fragment_json:
        fragment_json["sponsor"] = nom_propre(fragment_json["sponsor"])
    if fragment_json:
        await session.execute(
            text(
                "UPDATE core.activite SET donnees = donnees || cast(:f as jsonb) "
                "WHERE id::text = :id"
            ),
            {"id": identifiant, "f": json.dumps(fragment_json)},
        )
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=MODULE,
        cible_type=MODULE,
        cible_id=identifiant,
        nouvelle={c: champs[c] for c in champs},
    )

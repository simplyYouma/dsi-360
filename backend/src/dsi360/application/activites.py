"""Cas d'usage des activités (création, transition d'état) — générique par module."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.activite import calculer_priorite
from dsi360.domain.etats import etat_initial, transition_autorisee
from dsi360.domain.sla import echeances
from dsi360.infrastructure import audit
from dsi360.infrastructure.repositories import activite as repo

_RESOLUS = {"Résolu", "Résolue"}
_CLOTURES = {"Clôturé", "Clôturée"}


class TransitionInterdite(Exception):
    """Transition d'état non autorisée par la machine à états du module."""


class ActiviteIntrouvable(Exception):
    """Activité inexistante (ou hors périmètre)."""


async def creer_activite(
    session: AsyncSession,
    module: str,
    *,
    titre: str,
    description: str | None,
    impact: int,
    urgence: int,
    categorie_id: str | None,
    direction_id: str | None,
    responsable_id: str | None,
    acteur: dict[str, Any],
) -> str:
    debut = datetime.now(UTC)
    priorite = calculer_priorite(impact, urgence)
    ech = echeances(priorite, debut)
    reference = await repo.prochaine_reference(session, module, debut.year)
    statut = etat_initial(module)

    identifiant = await repo.creer(
        session,
        {
            "reference": reference,
            "module": module,
            "titre": titre,
            "description": description,
            "direction_id": direction_id,
            "categorie_id": categorie_id,
            "demandeur_id": acteur["id"],
            "responsable_id": responsable_id,
            "impact": impact,
            "urgence": urgence,
            "priorite": priorite,
            "statut": statut,
            "sla_prise_en_charge_le": ech.prise_en_charge_le,
            "sla_resolution_le": ech.resolution_le,
        },
    )
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=module,
        cible_type=module,
        cible_id=reference,
        nouvelle={"reference": reference, "titre": titre, "priorite": priorite, "statut": statut},
    )
    return identifiant


async def transition(
    session: AsyncSession,
    module: str,
    identifiant: str,
    vers: str,
    acteur: dict[str, Any],
) -> None:
    courant = await repo.par_id(session, module, identifiant)
    if courant is None:
        raise ActiviteIntrouvable
    depuis = courant["statut"]
    if not transition_autorisee(module, depuis, vers):
        raise TransitionInterdite(f"{depuis} → {vers}")

    maintenant = datetime.now(UTC)
    horodatages: dict[str, datetime] = {}
    if depuis == etat_initial(module):
        horodatages["pris_en_charge_le"] = maintenant
    if vers in _RESOLUS:
        horodatages["resolu_le"] = maintenant
    if vers in _CLOTURES:
        horodatages["cloture_le"] = maintenant

    await repo.changer_statut(session, identifiant, vers, horodatages)
    await audit.consigner(
        session,
        action="TRANSITION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=module,
        cible_type=module,
        cible_id=courant["reference"],
        ancienne={"statut": depuis},
        nouvelle={"statut": vers},
    )

"""Cas d'usage des tâches : CRUD + recalcul de l'avancement et du cycle de vie de l'activité.

L'avancement d'un projet = % de tâches terminées (source de vérité = les tâches, jamais saisi
à la main). Dès qu'une tâche existe, un projet en « Cadrage » passe automatiquement « En cours » ;
la clôture reste manuelle (décision COPIL).
"""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.activites import transition
from dsi360.application.notifications import notifier
from dsi360.infrastructure import audit
from dsi360.infrastructure.repositories import activite as activite_repo
from dsi360.infrastructure.repositories import tache as repo

# Passage automatique du cycle de vie piloté par les tâches. La clôture / les jalons de validation
# (CAB, ECAB, revue post-implémentation…) n'y figurent JAMAIS : ils restent manuels.
# _AUTO_DEMARRAGE : dès qu'au moins une tâche existe, on quitte l'état de départ.
_AUTO_DEMARRAGE: dict[str, tuple[str, str]] = {
    "projet": ("Cadrage", "En cours"),
    "changement": ("Planifié", "En implémentation"),
}
# _AUTO_ACHEVEMENT : quand 100 % des tâches sont terminées, on avance depuis l'état de départ.
# (Projet : pas d'achèvement auto — la clôture est décidée en COPIL.)
_AUTO_ACHEVEMENT: dict[str, tuple[str, str]] = {
    "changement": ("En implémentation", "Implémenté"),
}


async def _recalculer(
    session: AsyncSession, activite_id: str, module: str, acteur: dict[str, Any]
) -> None:
    total, terminees = await repo.compter(session, activite_id)
    avancement = round(100 * terminees / total) if total else 0
    # Mise à jour de l'avancement sans commit (le routeur committe l'ensemble d'un bloc).
    await session.execute(
        text(
            "UPDATE core.activite SET donnees = donnees || cast(:f as jsonb) WHERE id::text = :id"
        ),
        {"id": activite_id, "f": json.dumps({"avancement": avancement})},
    )
    if total == 0:
        return
    a = await activite_repo.par_id(session, module, activite_id)
    if a is None:
        return
    demarrage = _AUTO_DEMARRAGE.get(module)
    if demarrage is not None and a["statut"] == demarrage[0]:
        await transition(session, module, activite_id, demarrage[1], acteur)
        return
    achevement = _AUTO_ACHEVEMENT.get(module)
    if achevement is not None and avancement == 100 and a["statut"] == achevement[0]:
        await transition(session, module, activite_id, achevement[1], acteur)


async def _notifier_assigne(
    session: AsyncSession, activite_id: str, titre_tache: str, assigne_id: str | None,
    acteur: dict[str, Any],
) -> None:
    """Prévient l'agent qui reçoit une tâche (interne + e-mail). Rien s'il se l'assigne lui-même."""
    if not assigne_id or assigne_id == acteur["id"]:
        return
    reference = await session.scalar(
        text("SELECT reference FROM core.activite WHERE id = cast(:a as uuid)"),
        {"a": activite_id},
    )
    await notifier(
        session,
        destinataire_id=assigne_id,
        activite_id=activite_id,
        type_="TACHE",
        titre=f"Tâche assignée — {reference}",
        message=f"« {titre_tache} » ({reference}) vous a été assignée.",
    )


async def creer_tache(
    session: AsyncSession,
    activite_id: str,
    module: str,
    champs: dict[str, Any],
    acteur: dict[str, Any],
) -> str:
    tache_id = await repo.creer(session, activite_id, champs)
    await _notifier_assigne(session, activite_id, champs["titre"], champs.get("assigne_id"), acteur)
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=module,
        cible_type="tache",
        cible_id=champs["titre"],
        nouvelle={"titre": champs["titre"], "assigne_id": champs.get("assigne_id")},
    )
    await _recalculer(session, activite_id, module, acteur)
    return tache_id


async def maj_tache(
    session: AsyncSession,
    tache: dict[str, Any],
    module: str,
    champs: dict[str, Any],
    acteur: dict[str, Any],
) -> None:
    await repo.maj(session, tache["id"], champs)
    # Réassignation d'une tâche : prévenir le nouveau porteur (pas si l'assigné n'a pas changé).
    if "assigne_id" in champs and champs["assigne_id"] != tache["assigne_id"]:
        await _notifier_assigne(
            session, tache["activite_id"], tache["titre"], champs["assigne_id"], acteur
        )
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=module,
        cible_type="tache",
        cible_id=tache["titre"],
        ancienne={"statut": tache["statut"], "assigne_id": tache["assigne_id"]},
        nouvelle={c: v for c, v in champs.items()},
    )
    await _recalculer(session, tache["activite_id"], module, acteur)


async def supprimer_tache(
    session: AsyncSession, tache: dict[str, Any], module: str, acteur: dict[str, Any]
) -> None:
    await repo.supprimer(session, tache["id"])
    await audit.consigner(
        session,
        action="SUPPRESSION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=module,
        cible_type="tache",
        cible_id=tache["titre"],
    )
    await _recalculer(session, tache["activite_id"], module, acteur)

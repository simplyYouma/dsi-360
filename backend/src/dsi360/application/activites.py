"""Cas d'usage des activités (création, transition d'état) — générique par module."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.notifications import notifier, notifier_acteurs
from dsi360.domain.activite import calculer_priorite
from dsi360.domain.changement import dossier_incomplet_pour
from dsi360.domain.etats import (
    cible_apres_decisions,
    est_porte_validation,
    etat_initial,
    transition_autorisee,
    transition_reservee,
)
from dsi360.domain.sla import echeances
from dsi360.domain.texte import nom_propre, phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.repositories import activite as repo
from dsi360.infrastructure.repositories import sla as sla_repo

_RESOLUS = {"Résolu", "Résolue"}
_CLOTURES = {"Clôturé", "Clôturée"}


def _en_dict(valeur: Any) -> dict[str, Any]:
    """Colonne `donnees` (jsonb) normalisée en dict, quel que soit le pilote."""
    if isinstance(valeur, str):
        valeur = json.loads(valeur)
    return dict(valeur) if isinstance(valeur, dict) else {}


async def _resoudre_demandeur(session: AsyncSession, nom: str | None) -> str | None:
    """Reconnaît (ou crée) le demandeur par son nom — même référentiel que l'import."""
    if nom is None or nom.strip() == "":
        return None
    ident = await session.scalar(
        text(
            "INSERT INTO core.demandeur (nom_complet) VALUES (:n) "
            "ON CONFLICT (lower(nom_complet)) DO UPDATE SET maj_le = now() RETURNING id::text"
        ),
        {"n": nom_propre(nom)},
    )
    return str(ident) if ident is not None else None


class TransitionInterdite(Exception):
    """Transition d'état non autorisée par la machine à états du module."""


class TransitionReservee(Exception):
    """Issue de validation réservée aux valideurs : pas de déclenchement manuel."""


class ActiviteIntrouvable(Exception):
    """Activité inexistante (ou hors périmètre)."""


class DossierIncomplet(Exception):
    """Pièces obligatoires manquantes pour l'étape visée (dossier RFC avant le CAB/ECAB)."""

    def __init__(self, manquantes: list[str]) -> None:
        self.manquantes = manquantes
        super().__init__(", ".join(manquantes))


class AucunValideur(Exception):
    """On soumet au comité une activité sans valideur : la décision serait alors impossible."""


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
    demandeur: str | None = None,
) -> str:
    debut = datetime.now(UTC)
    priorite = calculer_priorite(impact, urgence)
    ech = echeances(priorite, debut, await sla_repo.charger_matrice(session, module))
    reference = await repo.prochaine_reference(session, module, debut.year)
    statut = etat_initial(module)
    demandeur_externe_id = await _resoudre_demandeur(session, demandeur)

    identifiant = await repo.creer(
        session,
        {
            "reference": reference,
            "module": module,
            "titre": phrase_propre(titre),
            "description": description,
            "direction_id": direction_id,
            "categorie_id": categorie_id,
            "demandeur_id": acteur["id"],
            "demandeur_externe_id": demandeur_externe_id,
            "responsable_id": responsable_id,
            "impact": impact,
            "urgence": urgence,
            "priorite": priorite,
            "statut": statut,
            "sla_prise_en_charge_le": ech.prise_en_charge_le,
            "sla_resolution_le": ech.resolution_le,
        },
    )
    # Notifie le responsable désigné à la création (sauf s'il est lui-même l'auteur).
    # Placé AVANT l'audit, qui committe la transaction (les notifications en profitent).
    if responsable_id is not None and responsable_id != acteur["id"]:
        await notifier(
            session,
            destinataire_id=responsable_id,
            activite_id=identifiant,
            type_="ASSIGNATION",
            titre=f"Nouvelle activité assignée — {reference}",
            message=f"{reference} « {phrase_propre(titre)} » vous a été assignée.",
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


async def reevaluer(
    session: AsyncSession,
    module: str,
    identifiant: str,
    *,
    impact: int | None,
    urgence: int | None,
    acteur: dict[str, Any],
) -> None:
    """Réévalue impact/urgence → recalcule priorité et échéances SLA (mesurées depuis la création).

    Corrige le pilotage SLA quand l'évaluation initiale était erronée. Journalise ancienne/nouvelle
    valeur (priorité comprise). Lève ``ActiviteIntrouvable`` si l'activité n'existe pas.
    """
    courant = await repo.par_id(session, module, identifiant)
    if courant is None:
        raise ActiviteIntrouvable
    nouvel_impact = impact if impact is not None else courant["impact"]
    nouvelle_urgence = urgence if urgence is not None else courant["urgence"]
    if nouvel_impact is None or nouvelle_urgence is None:
        raise ValueError("Impact et urgence sont requis pour évaluer la priorité.")
    priorite = calculer_priorite(nouvel_impact, nouvelle_urgence)
    ech = echeances(priorite, courant["cree_le"], await sla_repo.charger_matrice(session, module))
    await repo.maj_evaluation(
        session,
        identifiant,
        impact=nouvel_impact,
        urgence=nouvelle_urgence,
        priorite=priorite,
        sla_prise_en_charge_le=ech.prise_en_charge_le,
        sla_resolution_le=ech.resolution_le,
    )
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=module,
        cible_type=module,
        cible_id=courant["reference"],
        ancienne={"impact": courant["impact"], "urgence": courant["urgence"],
                  "priorite": courant["priorite"]},
        nouvelle={"impact": nouvel_impact, "urgence": nouvelle_urgence, "priorite": priorite},
    )


async def appliquer_decisions(
    session: AsyncSession, module: str, identifiant: str, acteur: dict[str, Any]
) -> str | None:
    """Enchaîne le workflow selon les décisions des valideurs (approbation ITIL).

    Approbation unanime → transition vers l'état validé ; un seul rejet → état de rejet. Ne fait
    rien si l'activité n'est pas dans un état d'attente de validation ou si des décisions manquent.
    Retourne l'état cible appliqué, ou ``None``.
    """
    courant = await repo.par_id(session, module, identifiant)
    if courant is None:
        return None
    valideurs = await repo.lister_valideurs(session, identifiant)
    cible = cible_apres_decisions(module, courant["statut"], [v["decision"] for v in valideurs])
    if cible is None:
        return None
    # force=True : c'est précisément la décision des valideurs qui autorise cette issue réservée.
    await transition(session, module, identifiant, cible, acteur, force=True)
    return cible


async def transition(
    session: AsyncSession,
    module: str,
    identifiant: str,
    vers: str,
    acteur: dict[str, Any],
    *,
    force: bool = False,
) -> None:
    courant = await repo.par_id(session, module, identifiant)
    if courant is None:
        raise ActiviteIntrouvable
    depuis = courant["statut"]
    if not transition_autorisee(module, depuis, vers):
        raise TransitionInterdite(f"{depuis} → {vers}")
    # Le comité (CAB/ECAB) ne délibère pas sur un dossier vide : impact, risque et plan de retour
    # arrière sont exigés par la procédure SI-12.04. Contrôle côté serveur : incontournable.
    manquantes = dossier_incomplet_pour(module, vers, _en_dict(courant["donnees"]))
    if manquantes:
        raise DossierIncomplet(manquantes)
    # Les issues de validation (CAB/ECAB, validation de demande) ne se poussent pas à la main :
    # elles passent par la décision des valideurs (appliquer_decisions, force=True).
    if not force and transition_reservee(module, depuis, vers):
        raise TransitionReservee(f"{depuis} → {vers}")
    # On n'entre pas au comité sans valideur : l'activité y resterait bloquée à vie, personne ne
    # pouvant approuver. On exige au moins un valideur désigné avant de soumettre.
    if not force and est_porte_validation(module, vers):
        if not await repo.lister_valideurs(session, identifiant):
            raise AucunValideur

    maintenant = datetime.now(UTC)
    horodatages: dict[str, datetime] = {}
    if depuis == etat_initial(module):
        horodatages["pris_en_charge_le"] = maintenant
    if vers in _RESOLUS:
        horodatages["resolu_le"] = maintenant
    if vers in _CLOTURES:
        horodatages["cloture_le"] = maintenant

    await repo.changer_statut(session, identifiant, vers, horodatages)
    # Notifie les acteurs du changement d'état AVANT l'audit (qui committe la transaction).
    await notifier_acteurs(
        session,
        activite_id=identifiant,
        type_="TRANSITION",
        titre=f"{courant['reference']} — {vers}",
        message=f"L'activité {courant['reference']} est passée à l'état « {vers} ».",
        exclure_id=acteur["id"],
    )
    # Entrée en validation (CAB/ECAB, validation de demande) : chaque valideur reçoit une demande
    # de décision dédiée — notification interne ET e-mail (selon sa préférence), pour qu'il agisse.
    if est_porte_validation(module, vers):
        for v in await repo.lister_valideurs(session, identifiant):
            await notifier(
                session,
                destinataire_id=str(v["id"]),
                activite_id=identifiant,
                type_="VALIDATION_REQUISE",
                titre=f"{courant['reference']} — à valider",
                message=(
                    f"Votre décision est attendue sur {courant['reference']} "
                    f"(état « {vers} ») : approuver ou rejeter."
                ),
            )
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

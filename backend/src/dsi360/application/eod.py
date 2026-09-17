"""Cas d'usage de l'EOD : ouvrir la soirée, pointer les étapes, en tirer l'état de la nuit.

Une soirée EOD n'est pas un dossier qu'on rédige mais un déroulé qu'on pointe. Deux conséquences
sur ce qui vit ici :

* **La soirée s'ouvre en un geste.** L'opérateur donne la date de la journée comptable à clore, le
  reste est déduit — le titre, la référence, les vingt-huit étapes du déroulé de référence. Lui
  demander de saisir un titre et un impact avant de pouvoir pointer sa première étape reviendrait
  à lui faire remplir un formulaire pendant que le core banking attend.

* **L'avancement se déduit, il ne se déclare pas.** Il est la part des étapes réglées. Le laisser
  saisir à la main créerait une seconde source pour un chiffre que les étapes disent déjà, et les
  deux divergeraient (c'est la raison pour laquelle la gouvernance, elle, n'a pas de tâches).
"""

import json
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.activite import calculer_priorite
from dsi360.domain.eod import (
    A_FAIRE,
    ANOMALIE,
    COMPLETE,
    EN_COURS,
    HORAIRE,
    INCIDENT,
    MODULE,
    NON_APPLICABLE,
    NOTE,
    avancement,
    compter_anomalies,
    manque_a_l_incident,
    resoudre_relance,
    reste_a_faire,
)
from dsi360.domain.etats import etat_initial
from dsi360.domain.sla import echeances
from dsi360.infrastructure import audit
from dsi360.infrastructure.repositories import activite as repo
from dsi360.infrastructure.repositories import eod as eod_repo
from dsi360.infrastructure.repositories import sla as sla_repo

#: Priorité par défaut d'une soirée ordinaire. Impact et urgence restent réévaluables : un arrêté
#: de fin d'exercice ne se pilote pas au même rythme qu'un mardi de novembre.
_IMPACT_DEFAUT = 4
_URGENCE_DEFAUT = 4


class JourneeDejaOuverte(Exception):
    """Une soirée couvre déjà cette date. Porte la référence pour pouvoir la nommer."""

    def __init__(self, reference: str) -> None:
        super().__init__(reference)
        self.reference = reference


def titre_journee(journee: date) -> str:
    """« EOD du 15/09/2026 » — lisible dans les listes mêlées, où le module n'est pas affiché."""
    return f"EOD du {journee.strftime('%d/%m/%Y')}"


async def ouvrir_journee(
    session: AsyncSession,
    *,
    journee: date,
    categorie_id: str | None,
    direction_id: str | None,
    responsable_id: str | None,
    impact: int | None,
    urgence: int | None,
    acteur: dict[str, Any],
) -> tuple[str, str, int]:
    """Ouvre la soirée d'une date et y pose le déroulé. Renvoie (id, référence, nb d'étapes).

    Lève ``JourneeDejaOuverte`` si une soirée couvre déjà cette nuit : deux rapports pour la même
    date seraient une faute de saisie, jamais une intention (l'index unique le garantit aussi en
    base, mais son message ne dirait pas laquelle des deux existe déjà).
    """
    jour = journee.isoformat()
    existante = await eod_repo.journee_existante(session, jour)
    if existante is not None:
        raise JourneeDejaOuverte(existante)

    maintenant = datetime.now(UTC)
    impact_retenu = impact or _IMPACT_DEFAUT
    urgence_retenue = urgence or _URGENCE_DEFAUT
    priorite = calculer_priorite(impact_retenu, urgence_retenue)
    ech = echeances(priorite, maintenant, await sla_repo.charger_matrice(session, MODULE))
    reference = await repo.prochaine_reference(session, MODULE, journee.year)
    statut = etat_initial(MODULE)

    identifiant = await repo.creer(
        session,
        {
            "reference": reference,
            "module": MODULE,
            "titre": titre_journee(journee),
            "description": None,
            "direction_id": direction_id,
            "categorie_id": categorie_id,
            "demandeur_id": acteur["id"],
            "responsable_id": responsable_id,
            "impact": impact_retenu,
            "urgence": urgence_retenue,
            "priorite": priorite,
            "statut": statut,
            "sla_prise_en_charge_le": ech.prise_en_charge_le,
            "sla_resolution_le": ech.resolution_le,
            # `journee` porte la date comptable close, et non la date de saisie : une soirée
            # commencée le 15 au soir se termine le 16 au matin. C'est elle qui fait l'unicité.
            "donnees": json.dumps({"journee": jour, "avancement": 0}),
        },
    )
    poses = await eod_repo.poser_le_deroule(session, identifiant)
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=MODULE,
        cible_type=MODULE,
        cible_id=reference,
        nouvelle={"reference": reference, "journee": jour, "statut": statut, "etapes": poses},
    )
    return identifiant, reference, poses


def pointage(quoi: str, etape: dict[str, Any], maintenant: datetime) -> dict[str, Any]:
    """Champs à écrire quand l'opérateur clique « Démarrer » ou « Terminer » sur une étape.

    Le geste fait deux choses à la fois, et c'est voulu : il horodate **et** il fait avancer le
    statut. Demander les deux séparément, à 21 h, sur vingt-huit lignes, c'est garantir des étapes
    horodatées restées « À faire » — le défaut exact du tableau qu'on remplace.

    Terminer une étape jamais démarrée lui pose aussi son heure de début : l'opérateur qui
    rattrape une ligne oubliée ne doit pas avoir à mentir sur l'heure ni à laisser un trou.
    """
    if quoi == "debut":
        return {"debut": maintenant, "statut": EN_COURS}
    # « Terminer » clôt le temps de l'étape, pas son verdict. Sur « Post EOFI_1 », le rapport
    # dit 19H53 → 20H08 ET « Branch 018 Error » : l'étape a fini — pour toutes les agences sauf
    # une — et reste en anomalie. Poser « Complété » ici effacerait ce que l'opérateur venait de
    # constater. L'anomalie est le seul verdict qu'une fin d'étape ne remplace pas.
    fixes: dict[str, Any] = {"fin": maintenant}
    if etape.get("statut") != ANOMALIE:
        fixes["statut"] = COMPLETE
    if etape.get("debut") is None:
        fixes["debut"] = maintenant
    return fixes


def preparer_relance(parent: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    """L'étape RELANCE que pose un incident d'agence, rattachée à l'étape qu'elle rejoue.

    Le rapport réel l'écrit ainsi : sous l'étape en anomalie, une ligne « RELANCE » avec son début,
    sa fin et son verdict. Une relance n'est donc pas une note en marge — c'est une étape qu'on
    pointe avec les mêmes gestes, comptée dans le même avancement, exportée sur la même ligne.

    Elle naît **En cours, depuis l'heure de relance** : consigner « relancée à 20H15 » dit que le
    traitement tourne depuis 20H15. L'opérateur la termine quand elle aboutit — ou la passe en
    anomalie si l'agence bloque encore, ce qui posera une seconde relance sous la première.
    """
    agence = str(observation.get("agence") or "").strip()
    return {
        "section": parent["section"],
        "libelle": f"RELANCE · {agence}" if agence else "RELANCE",
        "nature": HORAIRE,
        # Le rang du parent : elle se range juste après lui, le déroulé n'est pas renuméroté.
        "ordre": parent["ordre"],
        "relance_de": parent["id"],
        "agence": agence or None,
        "debut": observation.get("relance_le"),
        "statut": EN_COURS,
    }


def etat_de_la_nuit(statuts: list[str]) -> dict[str, int]:
    """Ce que les étapes disent de la soirée : avancement, reste à faire, anomalies."""
    return {
        "avancement": avancement(statuts),
        "reste": reste_a_faire(statuts),
        "anomalies": compter_anomalies(statuts),
        "etapes": len(statuts),
    }


async def rafraichir_avancement(session: AsyncSession, activite_id: str) -> dict[str, int]:
    """Recalcule l'avancement d'après les étapes et le range dans `donnees`.

    Stocké et non recalculé à chaque lecture : la liste des soirées affiche l'avancement de
    quinze nuits, et aller compter les étapes de chacune ferait quinze requêtes pour un chiffre.
    """
    etat = etat_de_la_nuit(await eod_repo.statuts(session, activite_id))
    await repo.maj_donnees(session, activite_id, {"avancement": etat["avancement"]})
    return etat


def cloture_conseillee(statuts: list[str]) -> str | None:
    """Statut de clôture que les étapes justifient, ou ``None`` si la soirée n'est pas finissable.

    Le serveur *conseille*, il ne décide pas : l'opérateur reste maître du verdict — une anomalie
    peut avoir été rattrapée hors du système, et lui seul le sait. Mais proposer « Clôturé » sur
    une nuit qui porte une anomalie serait l'inviter à effacer ce qu'il vient de constater.
    """
    if reste_a_faire(statuts) > 0:
        return None
    return "Clôturé avec réserves" if compter_anomalies(statuts) > 0 else "Clôturé"


#: Statuts d'étape qui demandent une explication. Une anomalie sans observation ne se relit pas :
#: six semaines plus tard, personne ne saura ce qui a coincé — ni si c'est reparti.
STATUTS_A_JUSTIFIER = frozenset({ANOMALIE, NON_APPLICABLE})


def justification_manquante(statut: str, observations: int) -> bool:
    """Un verdict qui sort de l'ordinaire et pas une ligne au journal de l'étape.

    On compte les observations plutôt qu'on ne relit un champ de notes : depuis que les
    observations s'historisent, l'explication est une **ligne de journal** — signée, horodatée,
    définitive. Une seule suffit ; c'est l'absence totale qu'on refuse.
    """
    return statut in STATUTS_A_JUSTIFIER and observations <= 0


class IncidentIncomplet(Exception):
    """Un incident d'agence auquel il manque l'agence ou l'heure de relance."""

    def __init__(self, manque: str) -> None:
        super().__init__(manque)
        self.manque = manque


class HeureIllisible(Exception):
    """L'heure de relance saisie ne se lit pas (« 01H12 », « 01:12 », « 0112 » sont attendus)."""

    def __init__(self, saisie: str) -> None:
        super().__init__(saisie)
        self.saisie = saisie


def preparer_observation(
    *,
    nature: str,
    agence: str | None,
    relance: str | None,
    texte: str,
    acteur: dict[str, Any],
    maintenant: datetime,
) -> dict[str, Any]:
    """Champs à écrire pour une observation, heure de relance résolue.

    L'opérateur tape « 01H12 », pas un horodatage ISO : c'est ce que lui affiche l'écran du core
    banking, et lui demander la date en plus, la nuit, serait lui faire recopier une évidence. La
    résolution — quelle **journée** porte cette heure — appartient au serveur : elle dépend de la
    règle « dernière occurrence passée », et une règle recopiée dans le navigateur finirait par
    en diverger.

    Une relance non saisie vaut **maintenant** quand l'observation est un incident : consigner un
    incident, c'est le consigner sur le moment. Lever une erreur là-dessus reviendrait à exiger
    une frappe de plus pour une information qu'on a déjà.
    """
    quand: datetime | None = None
    if (relance or "").strip():
        quand = resoudre_relance(relance or "", maintenant)
        if quand is None:
            raise HeureIllisible(relance or "")
    elif nature == INCIDENT:
        quand = maintenant

    propre = (agence or "").strip() or None
    if nature == INCIDENT:
        manque = manque_a_l_incident(propre, quand)
        if manque is not None:
            raise IncidentIncomplet(manque)
    return {
        "nature": nature,
        "agence": propre,
        "relance_le": quand,
        "texte": texte.strip(),
        "auteur_id": acteur["id"],
        "auteur_email": acteur["email"],
    }


__all__ = [
    "A_FAIRE",
    "INCIDENT",
    "NOTE",
    "HeureIllisible",
    "IncidentIncomplet",
    "JourneeDejaOuverte",
    "STATUTS_A_JUSTIFIER",
    "cloture_conseillee",
    "etat_de_la_nuit",
    "justification_manquante",
    "ouvrir_journee",
    "pointage",
    "preparer_observation",
    "rafraichir_avancement",
    "titre_journee",
]

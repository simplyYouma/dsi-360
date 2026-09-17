"""Règles de domaine de l'EOD — le traitement de fin de journée du système bancaire.

L'EOD (*End of Day*) est la coupure quotidienne du core banking : on arrête les flux entrants,
on sauvegarde, on bascule la date système au jour suivant, on lance les traitements de clôture
agence par agence, puis on rouvre les canaux. Une journée comptable ne s'ouvre pas tant que la
précédente n'est pas close : c'est l'activité la plus contrainte de la production, et la seule
qui se rejoue **à l'identique tous les soirs**.

D'où la forme retenue, différente des autres modules : une **journée EOD** n'est pas un dossier
qu'on rédige, c'est un **déroulé qu'on pointe**. Chaque étape porte son heure de début, son heure
de fin et son verdict. Le rapport envoyé le soir à la hiérarchie n'est plus retapé dans un
tableur : il *est* la fiche.

Ce fichier est la source de vérité du déroulé de référence (`DEROULE_REFERENCE`). Il est recopié
en étapes réelles à la création de chaque journée — comme les jalons d'un projet (cf.
``infrastructure/repositories/modele_jalon``) : une fois posées, les étapes appartiennent à la
journée et se corrigent librement. Retoucher le modèle ne réécrit jamais une soirée passée.
"""

import re
from datetime import datetime, timedelta
from typing import Final, NamedTuple

MODULE: Final = "eod"

# --- Statuts d'étape -----------------------------------------------------------------------------
#
# Volontairement distincts des statuts d'activité : ils décrivent un geste technique, pas un cycle
# de vie. Le rapport de la banque n'en connaît que trois — « Complete », un commentaire d'anomalie,
# et « X » pour ce qui ne s'applique pas ce soir-là. On ajoute les deux états d'avant le verdict,
# sans lesquels une soirée en cours ne serait pas lisible.

A_FAIRE: Final = "À faire"
EN_COURS: Final = "En cours"
COMPLETE: Final = "Complété"
ANOMALIE: Final = "Anomalie"
NON_APPLICABLE: Final = "Non applicable"

STATUTS_ETAPE: Final[tuple[str, ...]] = (
    A_FAIRE,
    EN_COURS,
    COMPLETE,
    ANOMALIE,
    NON_APPLICABLE,
)

#: Étapes dont le sort est réglé : elles ne sont plus attendues ce soir.
STATUTS_REGLES: Final = frozenset({COMPLETE, ANOMALIE, NON_APPLICABLE})

# --- Nature d'une étape --------------------------------------------------------------------------
#
# La quasi-totalité des étapes se pointe en heures. Deux font exception : « System Date », relevée
# avant puis après la bascule, où ce qui compte n'est pas *quand* on a regardé mais **ce qu'on a
# lu**. Les noyer dans les colonnes Début/Fin, c'est perdre la seule information qu'elles portent —
# et c'est précisément la vérification qui dit si l'EOD a réellement basculé la date.

HORAIRE: Final = "horaire"
VALEUR: Final = "valeur"
NATURES_ETAPE: Final[tuple[str, ...]] = (HORAIRE, VALEUR)


class EtapeModele(NamedTuple):
    """Une étape du déroulé de référence."""

    section: str
    libelle: str
    nature: str = HORAIRE
    #: Ce que l'opérateur doit vérifier, quand le libellé seul ne suffit pas à le dire.
    aide: str | None = None


# --- Sections ------------------------------------------------------------------------------------
#
# Les intitulés restent ceux du rapport envoyé chaque soir — y compris « PART 1 » à « PART 4 » et
# les noms de batchs en majuscules. Ce vocabulaire est celui des écrans du core banking : le
# traduire obligerait l'opérateur à faire la correspondance de tête, la nuit, sous contrainte.

PREPARATION: Final = "Préparation"
PART_1: Final = "PART 1"
PART_2: Final = "PART 2"
PART_3: Final = "PART 3"
PART_4: Final = "PART 4"
ADDITIONNELLES: Final = "Tâches additionnelles"

SECTIONS: Final[tuple[str, ...]] = (
    PREPARATION,
    PART_1,
    PART_2,
    PART_3,
    PART_4,
    ADDITIONNELLES,
)

# --- Le déroulé de référence ---------------------------------------------------------------------
#
# Relevé sur le rapport EOD réel d'AFG Bank Mali. L'ordre est celui de l'exécution : il ne se
# réarrange pas au hasard, chaque étape suppose la précédente faite.

DEROULE_REFERENCE: Final[tuple[EtapeModele, ...]] = (
    EtapeModele(PREPARATION, "Intégration fichier CARTHAGO"),
    EtapeModele(PREPARATION, "Check Pending Transactions"),
    EtapeModele(PREPARATION, "Backup before EOD"),
    # Sans aide : un soir ordinaire, la marque « Non applicable » dit déjà tout.
    EtapeModele(PREPARATION, "Backup before EOM"),
    EtapeModele(PREPARATION, "Stop Bank To Wallet"),
    EtapeModele(PREPARATION, "Date Check"),
    EtapeModele(
        PREPARATION,
        "System Date",
        nature=VALEUR,
        aide="Date système AVANT la bascule : la journée comptable qu'on s'apprête à clore.",
    ),
    EtapeModele(PREPARATION, "EODM"),
    EtapeModele(PREPARATION, "Check Batch CSSJOBBR --- AC-DAHOFF"),
    EtapeModele(PREPARATION, "Check Batch SMSJOBBR --- BRNSCH"),
    EtapeModele(PART_1, "Post EOFI_1 for all branch including 000 BAM"),
    EtapeModele(PART_2, "EOD till Post EOFI_3 for branch 000 BHO"),
    EtapeModele(PART_3, "EOD till Post MARKBOD for all branches"),
    EtapeModele(PART_4, "EOD till last stage for all branches POSTEOPD3"),
    EtapeModele(ADDITIONNELLES, "Date Checking"),
    EtapeModele(ADDITIONNELLES, "Batch Check : EMS_IN, EMS_OUT, EMS_OUT_PM"),
    EtapeModele(ADDITIONNELLES, "Batch Check : EXT_ASYNCCALL, NOTIF"),
    EtapeModele(ADDITIONNELLES, "AC-DAHOFF"),
    EtapeModele(ADDITIONNELLES, "BALANCE REPORT"),
    EtapeModele(ADDITIONNELLES, "INTERIM STATEMENT"),
    EtapeModele(ADDITIONNELLES, "SWIFT_UPLOAD"),
    EtapeModele(ADDITIONNELLES, "FETCHINCOMINGMESSAGES"),
    EtapeModele(ADDITIONNELLES, "PR_BG_GEN_MSG_OUT"),
    EtapeModele(ADDITIONNELLES, "BRNRPLI"),
    EtapeModele(ADDITIONNELLES, "PMSAJBPR"),
    EtapeModele(
        ADDITIONNELLES,
        "System Date",
        nature=VALEUR,
        aide="Date système APRÈS la bascule : elle doit afficher le jour suivant.",
    ),
    EtapeModele(ADDITIONNELLES, "Bank To Wallet Activation"),
    EtapeModele(ADDITIONNELLES, "Backup After EOD"),
)

# --- Observations : ce qui s'est dit pendant l'étape ----------------------------------------------
#
# Une soirée ne se raconte pas en une phrase. Sur « PART 3 — EOD till Post MARKBOD for all
# branches », une agence bloque, on relance ; une autre bloque vingt minutes plus tard, on relance
# encore. Un champ unique réécrit à chaque fois ne garde que la dernière phrase tapée — et perd
# l'heure, l'auteur et l'agence, c'est-à-dire tout ce qu'on vient chercher au matin.
#
# Deux natures, et non un simple drapeau : l'incident d'agence est une forme à part entière, que
# le rapport présente autrement et que les compteurs additionnent. Il porte trois informations que
# la hiérarchie réclame — quelle agence, à quelle heure on a relancé, ce qui a été fait — et la
# base refuse qu'il en manque une.

NOTE: Final = "note"
#: Quelque chose a coincé sur l'étape — sans que l'étape n'en soit moins finie. Le rapport réel :
#: « Completed For All Branch Expected Branch 018 Error » — elle a fini ET elle porte l'erreur.
#: L'anomalie est donc une ligne du journal, pas un verdict : on en ajoute autant qu'il en
#: survient, l'étape garde son pointage.
ANOMALIE_OBS: Final = "anomalie"
INCIDENT: Final = "incident"
NATURES_OBSERVATION: Final[tuple[str, ...]] = (NOTE, ANOMALIE_OBS, INCIDENT)
#: Les natures qui comptent comme anomalies de la nuit : l'incident d'agence en est une — avec
#: une agence et une relance en plus.
NATURES_ANOMALIE: Final = frozenset({ANOMALIE_OBS, INCIDENT})

#: « 01H12 », « 01h12 », « 01:12 », « 0112 » : l'opérateur tape l'heure comme elle lui vient.
_HEURE = re.compile(r"^(\d{1,2})\s*[:hH]?\s*(\d{2})$")

#: Marge d'avance tolérée avant de rejeter l'heure sur la veille. Une montre en avance de deux
#: minutes ne doit pas faire dater la relance de vingt-quatre heures plus tôt.
_AVANCE_TOLEREE: Final = timedelta(minutes=5)


def resoudre_relance(saisie: str, maintenant: datetime) -> datetime | None:
    """« 01H12 » → l'horodatage complet correspondant. ``None`` si l'heure est illisible.

    L'EOD franchit minuit — c'est son objet même. Une heure nue ne désigne donc pas forcément
    aujourd'hui : à 01H30 le 16, « 23H50 » parle de la veille au soir. On retient la **dernière
    occurrence passée**, jamais la prochaine : une relance se consigne après coup.
    """
    trouve = _HEURE.match(saisie.strip())
    if trouve is None:
        return None
    heures, minutes = int(trouve.group(1)), int(trouve.group(2))
    if heures > 23 or minutes > 59:
        return None
    local = maintenant.astimezone()
    candidat = local.replace(hour=heures, minute=minutes, second=0, microsecond=0)
    if candidat > local + _AVANCE_TOLEREE:
        candidat -= timedelta(days=1)
    return candidat


def manque_a_l_incident(agence: str | None) -> str | None:
    """Ce qui manque à un incident d'agence pour être un compte rendu, ou ``None`` s'il est complet.

    Rendre un message plutôt qu'un booléen : « il manque quelque chose » n'aide personne à 2 h du
    matin. La base porte la même règle (``ck_eod_observation_incident``) — ici on la dit, là-bas
    on la garantit.

    L'heure n'en fait plus partie : l'observation dit l'agence et ce qui a été fait, la ligne
    RELANCE — que l'opérateur démarre lui-même — dit quand. Poser une heure d'office à la saisie
    faisait lire un démarrage automatique là où il n'y en avait pas.
    """
    if not (agence or "").strip():
        return "l'agence concernée"
    return None


# --- Lecture d'une soirée ------------------------------------------------------------------------


def ordre_section(section: str) -> int:
    """Rang d'une section dans le déroulé. Une section inconnue passe en fin de liste.

    Les sections ajoutées à la main (une opération exceptionnelle, un rattrapage) ne cassent donc
    pas l'affichage : elles se rangent après le déroulé connu au lieu de s'y intercaler.
    """
    try:
        return SECTIONS.index(section)
    except ValueError:
        return len(SECTIONS)


def avancement(statuts: list[str]) -> int:
    """Part de la soirée réglée, en pourcentage (0..100).

    « Non applicable » compte comme réglé : un soir sans fin de mois n'est pas un soir à 96 %.
    """
    if not statuts:
        return 0
    regles = sum(1 for s in statuts if s in STATUTS_REGLES)
    return round(regles * 100 / len(statuts))


def reste_a_faire(statuts: list[str]) -> int:
    """Nombre d'étapes dont le sort n'est pas réglé."""
    return sum(1 for s in statuts if s not in STATUTS_REGLES)


def compter_anomalies(statuts: list[str]) -> int:
    return sum(1 for s in statuts if s == ANOMALIE)

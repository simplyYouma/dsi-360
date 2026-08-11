"""Revue périodique : cadence d'un contrôle (risque, accès, engagement) et calcul de l'échéance
suivante. Pur, sans dépendance infrastructure. Cf. docs/02-DOMAIN-MODEL.
"""

import calendar
from datetime import date, timedelta
from typing import Any

# Cadence (en jours) des revues rapprochées. Une revue quotidienne ou hebdomadaire ne s'exprime
# pas en mois : elle suit le calendrier réel (une surveillance de vulnérabilité, une revue
# d'accès sensibles se tiennent au jour ou à la semaine, pas au mois arrondi).
JOURS_PAR_PERIODICITE: dict[str, int] = {
    "Journalière": 1,
    "Hebdomadaire": 7,
}

# Cadence (en mois) des revues espacées. Le décalage en mois borne le jour au dernier du mois
# cible (31 → 30/28) : c'est ce qu'on attend d'une échéance mensuelle.
MOIS_PAR_PERIODICITE: dict[str, int] = {
    "Mensuelle": 1,
    "Trimestrielle": 3,
    "Semestrielle": 6,
    "Annuelle": 12,
}

#: Toutes les périodicités, de la plus rapprochée à la plus espacée — l'ordre d'affichage.
PERIODICITES: tuple[str, ...] = (
    *JOURS_PAR_PERIODICITE,
    *MOIS_PAR_PERIODICITE,
)

# Les trois clés du cycle de revue, portées par `donnees`. Retirer la périodicité les efface toutes.
CLES_REVUE = ("periodicite", "prochaine_revue", "derniere_revue")


def _ajouter_mois(depart: date, mois: int) -> date:
    """Décale d'un nombre de mois en bornant le jour au dernier jour du mois cible (31 → 30/28)."""
    index = depart.month - 1 + mois
    annee = depart.year + index // 12
    mois_cible = index % 12 + 1
    jour = min(depart.day, calendar.monthrange(annee, mois_cible)[1])
    return date(annee, mois_cible, jour)


def prochaine_revue(periodicite: str, depuis: date) -> date:
    """Date de la revue suivante, une cadence après `depuis`.

    Les cadences rapprochées (journalière, hebdomadaire) se comptent en jours ; les autres en
    mois. Lève ``ValueError`` si la périodicité est inconnue : sans cadence, aucune échéance n'a
    de sens.
    """
    jours = JOURS_PAR_PERIODICITE.get(periodicite)
    if jours is not None:
        return depuis + timedelta(days=jours)
    mois = MOIS_PAR_PERIODICITE.get(periodicite)
    if mois is None:
        raise ValueError(f"Périodicité inconnue : {periodicite}")
    return _ajouter_mois(depuis, mois)


def calculer_planification(
    corps: dict[str, Any], aujourdhui: date
) -> tuple[dict[str, Any], list[str]]:
    """À partir de ce que l'acteur a saisi, ce qu'il faut écrire et ce qu'il faut effacer.

    La périodicité pilote le cycle — tout en découle. Deux règles, une seule vérité :

    - **Périodicité posée** : elle fixe la première échéance (aujourd'hui + cadence) si l'acteur
      n'a pas fourni de date. Choisir la cadence suffit donc à programmer la revue.
    - **Périodicité retirée** (mise à vide) : le cycle se ferme. On efface *toutes* les clés de
      revue — on ne laisse jamais une date orpheline, qui afficherait une échéance qu'aucune
      cadence ne pilote et qu'on ne pourrait pas clore.

    Renvoie ``(fragment_à_fusionner, clés_à_effacer)``. Pur : aucune I/O, testable seul.
    """
    fragment = dict(corps)
    if "periodicite" in fragment:
        if fragment["periodicite"]:
            if "prochaine_revue" not in fragment:
                fragment["prochaine_revue"] = prochaine_revue(
                    str(fragment["periodicite"]), aujourdhui
                ).isoformat()
        else:
            # Retrait de la périodicité : rien à écrire, tout le cycle à effacer.
            return {}, list(CLES_REVUE)
    return fragment, []

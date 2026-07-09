"""Revue périodique : cadence d'un contrôle (risque, accès, engagement) et calcul de l'échéance
suivante. Pur, sans dépendance infrastructure. Cf. docs/02-DOMAIN-MODEL.
"""

import calendar
from datetime import date

# Cadence (en mois) de chaque périodicité paramétrable.
MOIS_PAR_PERIODICITE: dict[str, int] = {
    "Mensuelle": 1,
    "Trimestrielle": 3,
    "Semestrielle": 6,
    "Annuelle": 12,
}


def _ajouter_mois(depart: date, mois: int) -> date:
    """Décale d'un nombre de mois en bornant le jour au dernier jour du mois cible (31 → 30/28)."""
    index = depart.month - 1 + mois
    annee = depart.year + index // 12
    mois_cible = index % 12 + 1
    jour = min(depart.day, calendar.monthrange(annee, mois_cible)[1])
    return date(annee, mois_cible, jour)


def prochaine_revue(periodicite: str, depuis: date) -> date:
    """Date de la revue suivante, `periodicite` mois après `depuis`.

    Lève ``ValueError`` si la périodicité est inconnue : sans cadence, aucune échéance n'a de sens.
    """
    mois = MOIS_PAR_PERIODICITE.get(periodicite)
    if mois is None:
        raise ValueError(f"Périodicité inconnue : {periodicite}")
    return _ajouter_mois(depuis, mois)

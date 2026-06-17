"""Règles de domaine sur l'activité : priorité (impact × urgence) et criticité des risques.

Conventions : impact, urgence, probabilité ∈ 1..5 (5 = le plus grave). La priorité est exprimée
P1..P5 (1 = critique, 5 = très faible). Tout est pur (aucune dépendance infrastructure) et
paramétrable au niveau supérieur. Cf. docs/02-DOMAIN-MODEL §2.
"""

MODULES: tuple[str, ...] = (
    "incident",
    "demande",
    "probleme",
    "changement",
    "projet",
    "audit",
    "risque",
)


def _borne(valeur: int, mini: int = 1, maxi: int = 5) -> int:
    if not mini <= valeur <= maxi:
        raise ValueError(f"Valeur {valeur} hors bornes [{mini}, {maxi}].")
    return valeur


def calculer_priorite(impact: int, urgence: int) -> int:
    """Combine impact et urgence (1..5, 5 = grave) en priorité P1..P5 (1 = critique).

    Plus l'impact et l'urgence sont élevés, plus la priorité est haute (P1).
    """
    _borne(impact)
    _borne(urgence)
    niveau = -(-(impact + urgence) // 2)  # moyenne arrondie au supérieur, 1..5
    return 6 - niveau


def calculer_criticite(probabilite: int, impact: int) -> int:
    """Criticité d'un risque IT : 1..5 (5 = critique), à partir de probabilité × impact."""
    _borne(probabilite)
    _borne(impact)
    return -(-(probabilite + impact) // 2)

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
    "cybersecurite",
    "gouvernance",
)

# Préfixe de référence lisible par module (ex. INC-2026-00042).
PREFIXE_REFERENCE: dict[str, str] = {
    "incident": "INC",
    "demande": "DEM",
    "probleme": "PRB",
    "changement": "CHG",
    "projet": "PRJ",
    "audit": "AUD",
    "risque": "RSQ",
    "cybersecurite": "CYB",
    "gouvernance": "GOV",
}


def _borne(valeur: int, mini: int = 1, maxi: int = 5) -> int:
    if not mini <= valeur <= maxi:
        raise ValueError(f"Valeur {valeur} hors bornes [{mini}, {maxi}].")
    return valeur


# Matrice de priorité ITIL (procédure SI-12.01) : bandes Impact × Urgence -> priorité P1..P5.
# Les niveaux 1..5 saisis sont regroupés en 3 bandes : 1-2 = Faible, 3 = Moyen, 4-5 = Élevé.
# Bande 3 = Élevé, 2 = Moyen, 1 = Faible.
_MATRICE_PRIORITE: dict[tuple[int, int], int] = {
    (3, 3): 1, (3, 2): 2, (3, 1): 3,
    (2, 3): 2, (2, 2): 3, (2, 1): 4,
    (1, 3): 3, (1, 2): 4, (1, 1): 5,
}


def _bande(niveau: int) -> int:
    """Regroupe un niveau 1..5 en bande ITIL : Élevé (3) / Moyen (2) / Faible (1)."""
    return 3 if niveau >= 4 else 2 if niveau == 3 else 1


def calculer_priorite(impact: int, urgence: int) -> int:
    """Priorité P1..P5 (1 = critique) selon la matrice ITIL impact × urgence (SI-12.01)."""
    _borne(impact)
    _borne(urgence)
    return _MATRICE_PRIORITE[(_bande(impact), _bande(urgence))]


def calculer_criticite(probabilite: int, impact: int) -> int:
    """Criticité d'un risque IT : 1..5 (5 = critique), à partir de probabilité × impact."""
    _borne(probabilite)
    _borne(impact)
    return -(-(probabilite + impact) // 2)

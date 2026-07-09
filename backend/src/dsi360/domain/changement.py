"""Dossier RFC d'un changement (ITIL, procédure SI-12.04).

Le CAB (et l'ECAB en urgence) autorise ou refuse une modification en production. Pour trancher,
le comité doit disposer d'un dossier minimal : ce qui est touché, ce qui peut mal tourner, et
comment revenir en arrière. Tant que ces pièces manquent, la demande ne peut pas lui être soumise.
Pur, sans dépendance infrastructure.
"""

from typing import Any

# États où siège le comité : au-delà, le dossier a déjà été instruit.
ETATS_COMITE: frozenset[str] = frozenset({"CAB", "ECAB"})

# Pièces exigées avant le passage en comité, dans l'ordre où on les demande à l'écran.
CHAMPS_REQUIS_COMITE: tuple[tuple[str, str], ...] = (
    ("analyse_impact", "l'analyse d'impact"),
    ("analyse_risque", "l'analyse de risque"),
    ("plan_retour_arriere", "le plan de retour arrière"),
)


def pieces_manquantes_comite(donnees: dict[str, Any]) -> list[str]:
    """Libellés des pièces du dossier RFC absentes ou vides. Liste vide = dossier recevable."""
    manquantes = []
    for champ, libelle in CHAMPS_REQUIS_COMITE:
        valeur = donnees.get(champ)
        if not isinstance(valeur, str) or not valeur.strip():
            manquantes.append(libelle)
    return manquantes


def dossier_incomplet_pour(
    module: str, vers: str, donnees: dict[str, Any]
) -> list[str]:
    """Pièces manquantes bloquant `vers`, ou liste vide si la transition ne l'exige pas."""
    if module != "changement" or vers not in ETATS_COMITE:
        return []
    return pieces_manquantes_comite(donnees)

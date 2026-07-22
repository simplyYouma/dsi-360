"""Lecture du fichier d'inventaire des équipements (.xlsx) — pur, sans accès base.

Le classeur mêle des colonnes comptables (code immo, taux, date et valeur d'acquisition, durée)
et des colonnes de terrain (matricule du détenteur, n° de série, modèle, emplacement). Ici on ne
fait que **lire et normaliser** ; c'est `application/import_equipements` qui décide ensuite ce
qu'un réimport a le droit d'écraser.

Les intitulés sont associés par leur libellé normalisé, jamais par leur position — et l'on
accepte les variantes rencontrées, **dont la faute de frappe « Designtion »** du fichier source.
"""

from io import BytesIO
from typing import Any

import openpyxl

from dsi360.infrastructure.classeur import (
    normaliser,
    parser_date,
    parser_entier,
    parser_nombre,
    trouver_entetes,
    valeur_cellule,
)

# Intitulé normalisé -> clé canonique. Plusieurs libellés peuvent mener à la même clé : les
# exports varient, et le fichier de référence porte « Designtion » (sic).
ENTETES = _ENTETES = {
    "code immo": "code_immo",
    "new code": "code_immo",
    "code immobilisation": "code_immo",
    "matricule": "matricule",
    "n° serie": "numero_serie",
    "n serie": "numero_serie",
    "numero de serie": "numero_serie",
    "numero serie": "numero_serie",
    "modele": "modele",
    "designtion": "designation",  # faute de frappe du fichier source
    "designation": "designation",
    "emplacement": "emplacement",
    "departement": "departement",
    "taux": "taux",
    "da": "date_acquisition",
    "date acquisition": "date_acquisition",
    "date d'acquisition": "date_acquisition",
    "duree": "duree_annees",
    "va": "valeur_acquisition",
    "valeur acquisition": "valeur_acquisition",
    "valeur d'acquisition": "valeur_acquisition",
    "etat bon": "etat_bon",
    "bon": "etat_bon",
    "rebut": "etat_rebut",
    "rebut ou casse": "etat_rebut",
    "casse": "etat_casse",
    "non retrouve": "etat_non_retrouve",
}

# Sans ces deux colonnes, ce n'est pas un fichier d'inventaire : mieux vaut le dire tout de suite
# que d'importer n'importe quoi.
REPERES = _REPERES = {"code_immo", "designation"}

#: Colonne d'état -> constat. Lu et compté, mais pas appliqué : l'état d'un équipement se consigne
#: dans une campagne d'inventaire (lot à venir), pas comme un attribut du matériel.
_ETATS = {
    "etat_bon": "BON",
    "etat_rebut": "REBUT",
    "etat_casse": "CASSE",
    "etat_non_retrouve": "NON_RETROUVE",
}


def _texte(valeur: Any) -> str | None:
    """Cellule texte nettoyée. ``None`` si vide — l'appelant écartera les fausses valeurs."""
    if valeur in (None, ""):
        return None
    propre = " ".join(str(valeur).split())
    return propre or None


def _coche(valeur: Any) -> bool:
    """Une case d'état cochée : « X », « x », « 1 », « oui »."""
    return normaliser(valeur) in {"x", "1", "oui", "o", "true"}


def analyser_classeur(contenu: bytes) -> list[dict[str, Any]]:
    """Lignes d'équipement normalisées. Les lignes sans désignation sont écartées.

    Lève ``ValueError`` si le fichier n'a pas la tête d'un inventaire : l'écran doit dire pourquoi
    plutôt que d'afficher « 0 importé ».
    """
    classeur = openpyxl.load_workbook(BytesIO(contenu), data_only=True, read_only=True)
    feuille = classeur.worksheets[0]
    lignes = list(feuille.iter_rows(values_only=True))
    debut, index = trouver_entetes(lignes, _ENTETES, _REPERES)

    equipements: list[dict[str, Any]] = []
    for ligne in lignes[debut + 1 :]:
        if ligne is None or not any(c not in (None, "") for c in ligne):
            continue
        designation = _texte(valeur_cellule(ligne, index, "designation"))
        if designation is None:
            # Sans désignation, l'équipement serait introuvable dans la liste : on l'ignore.
            continue
        date_acquisition = parser_date(valeur_cellule(ligne, index, "date_acquisition"))
        etats = [
            constat
            for cle, constat in _ETATS.items()
            if _coche(valeur_cellule(ligne, index, cle))
        ]
        equipements.append(
            {
                "code_immo": _texte(valeur_cellule(ligne, index, "code_immo")),
                "designation": designation,
                "matricule": _texte(valeur_cellule(ligne, index, "matricule")),
                "numero_serie": _texte(valeur_cellule(ligne, index, "numero_serie")),
                "modele": _texte(valeur_cellule(ligne, index, "modele")),
                "emplacement": _texte(valeur_cellule(ligne, index, "emplacement")),
                "departement": _texte(valeur_cellule(ligne, index, "departement")),
                "taux": parser_nombre(valeur_cellule(ligne, index, "taux")),
                "date_acquisition": date_acquisition.date() if date_acquisition else None,
                "duree_annees": parser_entier(valeur_cellule(ligne, index, "duree_annees")),
                "valeur_acquisition": parser_nombre(
                    valeur_cellule(ligne, index, "valeur_acquisition")
                ),
                # Premier état coché seulement : deux cases cochées sur la même ligne est une
                # contradiction du fichier, pas une information à démultiplier.
                "etat_constate": etats[0] if etats else None,
            }
        )
    return equipements

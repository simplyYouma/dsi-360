"""Briques communes de lecture d'un classeur Excel importé.

Les fichiers que reçoit la DSI (rapport ServiceDesk, inventaire comptable) partagent les mêmes
travers : un préambule avant la vraie ligne d'en-têtes, des intitulés qui changent de casse et
d'accents d'un export à l'autre, parfois une faute de frappe. On associe donc les colonnes par
leur **intitulé normalisé**, jamais par leur position.
"""

import unicodedata
from datetime import datetime
from typing import Any


def normaliser(valeur: Any) -> str:
    """Intitulé comparable : sans accents, sans casse, espaces réduits."""
    texte = str(valeur or "").strip().replace("’", "'").lower()
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    )
    return " ".join(sans_accent.split())


def parser_date(valeur: Any) -> datetime | None:
    """Date d'une cellule : objet Excel natif, ou texte au format français."""
    if valeur in (None, ""):
        return None
    if isinstance(valeur, datetime):
        return valeur
    texte = str(valeur).strip()
    for motif in ("%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texte, motif)
        except ValueError:
            continue
    return None


def parser_nombre(valeur: Any) -> float | None:
    """Montant ou taux : accepte « 23 074 595 », « 12,5 », « 25% ». ``None`` si illisible."""
    if valeur in (None, ""):
        return None
    if isinstance(valeur, int | float):
        return float(valeur)
    # Espaces (y compris insécables) et % retirés ; virgule décimale ramenée au point.
    texte = str(valeur).replace(" ", "").replace(" ", "").replace("%", "").replace(",", ".")
    try:
        return float(texte)
    except ValueError:
        return None


def parser_entier(valeur: Any) -> int | None:
    """Premier nombre entier trouvé : « 4 ans » -> 4. ``None`` si la cellule n'en contient pas."""
    if valeur in (None, ""):
        return None
    if isinstance(valeur, int | float):
        return int(valeur)
    chiffres = "".join(c for c in str(valeur) if c.isdigit())
    return int(chiffres) if chiffres else None


def trouver_entetes(
    lignes: list[tuple[Any, ...]], alias: dict[str, str], reperes: set[str], limite: int = 40
) -> tuple[int, dict[str, int]]:
    """Repère la ligne d'en-têtes et l'index de chaque colonne connue.

    ``reperes`` : les clés canoniques qui doivent toutes être présentes pour reconnaître la ligne
    d'en-têtes — sans quoi un préambule contenant un mot isolé pourrait être pris pour elle.
    """
    for i, ligne in enumerate(lignes[:limite]):
        index: dict[str, int] = {}
        for j, cellule in enumerate(ligne):
            cle = alias.get(normaliser(cellule))
            if cle is not None and cle not in index:
                index[cle] = j
        if reperes <= index.keys():
            return i, index
    attendus = ", ".join(sorted(reperes))
    raise ValueError(f"En-têtes introuvables : colonnes {attendus} attendues.")


def lignes_de(feuille: Any, limite: int | None = None) -> list[tuple[Any, ...]]:
    """Lignes d'une feuille, éventuellement bornées (lecture d'en-têtes)."""
    lues: list[tuple[Any, ...]] = []
    for ligne in feuille.iter_rows(values_only=True):
        lues.append(ligne)
        if limite is not None and len(lues) >= limite:
            break
    return lues


def feuille_avec_entetes(
    classeur: Any, alias: dict[str, str], reperes: set[str]
) -> tuple[list[tuple[Any, ...]], int, dict[str, int]]:
    """Première feuille du classeur qui porte la ligne d'en-têtes attendue.

    Les exports ne mettent pas toujours les données sur la première feuille (page de filtres,
    sommaire…). On cherche donc partout plutôt que de refuser un fichier valide.
    """
    for feuille in classeur.worksheets:
        lignes = lignes_de(feuille)
        try:
            debut, index = trouver_entetes(lignes, alias, reperes)
        except ValueError:
            continue
        return lignes, debut, index
    attendus = ", ".join(sorted(reperes))
    raise ValueError(f"En-têtes introuvables : colonnes {attendus} attendues.")


def apercu_intitules(classeur: Any, limite: int = 12) -> str:
    """Ce que le classeur donne à lire en tête de sa première feuille.

    Sert aux messages d'erreur : « fichier non reconnu » n'aide personne, « voici les intitulés
    que j'ai lus » se corrige.
    """
    feuille = classeur.worksheets[0]
    textes: list[str] = []
    for ligne in lignes_de(feuille, 8):
        for cellule in ligne:
            texte = " ".join(str(cellule).split()) if cellule is not None else ""
            if texte and texte not in textes:
                textes.append(texte)
        if len(textes) >= limite:
            break
    return " · ".join(textes[:limite]) or "(aucun intitulé lisible)"


def valeur_cellule(ligne: tuple[Any, ...], index: dict[str, int], cle: str) -> Any:
    """Cellule d'une ligne pour une clé canonique, ``None`` si la colonne est absente."""
    j = index.get(cle)
    return None if j is None or j >= len(ligne) else ligne[j]

"""Génération de fichiers d'export : CSV (stdlib) et Excel (openpyxl)."""

import csv
import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def vers_csv(entetes: list[str], lignes: list[list[Any]]) -> bytes:
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";")
    ecrivain.writerow(entetes)
    ecrivain.writerows(lignes)
    # BOM UTF-8 pour qu'Excel ouvre correctement les accents.
    return tampon.getvalue().encode("utf-8-sig")


def vers_xlsx(
    entetes: list[str], lignes: list[list[Any]], titre: str, *, retour_ligne: bool = False
) -> bytes:
    """Classeur d'une seule feuille.

    ``retour_ligne`` : une cellule peut contenir plusieurs lignes — le journal d'observations d'une
    étape EOD, par exemple. Sans lui, Excel affiche le tout sur une seule ligne tronquée et la
    largeur de colonne se calcule sur la chaîne entière : deux défauts qui rendent la colonne
    illisible. Il reste optionnel pour ne rien changer aux exports dont les cellules tiennent
    naturellement sur une ligne.
    """
    classeur = Workbook()
    feuille = classeur.active
    assert feuille is not None  # un classeur neuf a toujours une feuille active  # noqa: S101
    feuille.title = titre[:31]  # Excel limite le nom d'onglet à 31 caractères

    feuille.append(entetes)
    gras = Font(bold=True, color="FFFFFF")
    fond = PatternFill("solid", fgColor="16181D")
    for cellule in feuille[1]:
        cellule.font = gras
        cellule.fill = fond

    for ligne in lignes:
        feuille.append(ligne)

    if retour_ligne:
        habillage = Alignment(wrap_text=True, vertical="top")
        for rangee in feuille.iter_rows(min_row=2):
            for cellule in rangee:
                cellule.alignment = habillage

    def _largeur(valeur: Any) -> int:
        # Avec l'habillage, c'est la ligne la plus longue qui décide de la largeur : mesurer la
        # chaîne entière donnerait une colonne au maximum pour un journal de trois courtes lignes.
        texte = str(valeur)
        if not retour_ligne:
            return len(texte)
        return max((len(part) for part in texte.splitlines()), default=0)

    for i, entete in enumerate(entetes, start=1):
        # get_column_letter gère au-delà de 26 colonnes (AA, AB…) ; chr(64+i) produisait des
        # lettres invalides. lignes ragged : on ne lit la cellule que si elle existe.
        largeurs = [len(entete)] + [_largeur(lg[i - 1]) for lg in lignes if len(lg) >= i]
        feuille.column_dimensions[get_column_letter(i)].width = min(max(largeurs) + 2, 50)

    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()

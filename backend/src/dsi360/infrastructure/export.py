"""Génération de fichiers d'export : CSV (stdlib) et Excel (openpyxl)."""

import csv
import io
from typing import Any

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ImageClasseur
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
    entetes: list[str],
    lignes: list[list[Any]],
    titre: str,
    *,
    retour_ligne: bool = False,
    bandeaux: set[int] | None = None,
    images: list[bytes] | None = None,
) -> bytes:
    """Classeur d'une seule feuille.

    ``retour_ligne`` : une cellule peut contenir plusieurs lignes — le journal d'observations d'une
    étape EOD, par exemple. Sans lui, Excel affiche le tout sur une seule ligne tronquée et la
    largeur de colonne se calcule sur la chaîne entière : deux défauts qui rendent la colonne
    illisible. Il reste optionnel pour ne rien changer aux exports dont les cellules tiennent
    naturellement sur une ligne.

    ``bandeaux`` : rangs (dans ``lignes``) qui sont des titres de section et non des données —
    « PART 1 », « PART 2 » du rapport EOD. Ils sont fusionnés sur toute la largeur et teintés,
    comme dans le document que la Production remettait déjà à la main.

    ``images`` : des captures (PNG/JPEG) posées SOUS le tableau, l'une après l'autre, à sa
    largeur — le rapport de la Production se terminait par la capture du core banking, preuve de
    ce qui est pointé au-dessus, et la hiérarchie la lit après le tableau.
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

    if bandeaux:
        vert_pale = PatternFill("solid", fgColor="E2F0D9")
        for rang in sorted(bandeaux):
            numero = rang + 2  # +1 pour l'en-tête, +1 car Excel compte à partir de 1
            feuille.merge_cells(
                start_row=numero, start_column=1, end_row=numero, end_column=len(entetes)
            )
            cellule = feuille.cell(row=numero, column=1)
            cellule.font = Font(bold=True)
            cellule.fill = vert_pale
            cellule.alignment = Alignment(horizontal="center")

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

    if images:
        # La largeur du tableau en pixels — Excel compte ses colonnes en caractères, ~7 px chacun.
        largeur_px = sum(
            int(feuille.column_dimensions[get_column_letter(i)].width * 7) + 5
            for i in range(1, len(entetes) + 1)
        )
        rang = feuille.max_row + 2
        for contenu in images:
            image = ImageClasseur(io.BytesIO(contenu))
            if image.width > 0:
                rapport = largeur_px / image.width
                image.width = largeur_px
                image.height = int(image.height * rapport)
            feuille.add_image(image, f"A{rang}")
            # Une ligne Excel fait 20 px par défaut : on saute autant de lignes que l'image en
            # couvre, plus une, pour que la suivante ne la chevauche pas.
            rang += int(image.height / 20) + 2

    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()

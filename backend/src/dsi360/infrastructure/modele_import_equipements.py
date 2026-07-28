"""Modèle Excel d'import d'inventaire : un classeur prêt à remplir par le métier.

Deux feuilles :
- **Inventaire** — la grille de saisie. La ligne d'en-tête reprend *exactement* les intitulés que
  l'import sait lire ; en dessous, tout est vide, prêt à remplir. Chaque en-tête porte une note
  (survol) qui dit à quoi sert la colonne et si elle est obligatoire.
- **Mode d'emploi** — la même chose en clair, plus la règle de création / mise à jour, pour qui
  n'ouvre pas les notes.

On ne met **aucune ligne d'exemple** dans la feuille de saisie : elle serait importée comme un vrai
équipement. Les exemples vivent dans le mode d'emploi, que l'import ignore (il ne lit que la feuille
portant les en-têtes).
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

# (en-tête EXACT — doit correspondre aux alias du lecteur —, obligatoire, largeur, aide de survol).
_COLONNES: tuple[tuple[str, bool, int, str], ...] = (
    ("Code immo", False, 16,
     "Code d'immobilisation comptable. C'est la CLÉ : une ligne dont le code existe déjà met à "
     "jour la fiche ; un code nouveau (ou vide) crée un équipement. Une ligne sans code ne peut "
     "pas être mise à jour au prochain import."),
    ("Désignation", True, 34,
     "OBLIGATOIRE. Ce qu'est le matériel (ex. « Ordinateur portable Dell Latitude 5540 »). "
     "Une ligne sans désignation est ignorée."),
    ("Type", False, 20,
     "Nature du matériel (Ordinateur portable, Serveur, Imprimante, Onduleur…). Créé "
     "automatiquement s'il n'existe pas encore. Facultatif."),
    ("N° série", False, 18, "Numéro de série constructeur. Facultatif."),
    ("Modèle", False, 20, "Référence du modèle (ex. Latitude 5540). Facultatif."),
    ("Emplacement", False, 22,
     "Où se trouve le matériel (Siège, Salle serveurs, Agence…). Créé automatiquement. "
     "Facultatif."),
    ("Département", False, 20, "Service rattaché. Créé automatiquement. Facultatif."),
    ("Matricule", False, 14,
     "Matricule de l'agent détenteur. Rapproché d'un compte s'il existe ; sinon conservé tel quel, "
     "en attendant. Facultatif."),
    ("Taux", False, 10, "Taux d'amortissement annuel, en % (ex. 25). Facultatif."),
    ("Date acquisition", False, 16,
     "Date d'achat (jj/mm/aaaa). Sert au calcul de l'amortissement."),
    ("Durée", False, 10, "Durée d'amortissement, en années (ex. 4). Facultatif."),
    ("Valeur acquisition", False, 18, "Prix d'achat en FCFA (ex. 850000). Facultatif."),
    ("État constaté", False, 16,
     "Dernier contrôle : Bon, Rebut ou Cassé. À laisser vide si le matériel n'a pas été vu. "
     "Une valeur ici vaut constat daté sur la fiche."),
)

_VERT = "7FC81F"          # vert de la marque, pour l'en-tête
_VERT_CLAIR = "EEF7DF"
_OBLIGATOIRE = "FDECEC"    # fond rosé pour signaler la colonne obligatoire
_NOIR = "16181D"


def _entete(feuille: Worksheet, colonnes: tuple[tuple[str, bool, int, str], ...]) -> None:
    """Pose la ligne d'en-tête stylée, avec largeur, note de survol et gel de la ligne."""
    gras_blanc = Font(bold=True, color="FFFFFF", size=11)
    fond = PatternFill("solid", fgColor=_VERT)
    fond_obl = PatternFill("solid", fgColor="C0392B")  # rouge sobre : la colonne à ne pas oublier
    centre = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for i, (titre, obligatoire, largeur, aide) in enumerate(colonnes, start=1):
        cellule = feuille.cell(row=1, column=i, value=titre)
        cellule.font = gras_blanc
        cellule.fill = fond_obl if obligatoire else fond
        cellule.alignment = centre
        note = Comment(("Colonne OBLIGATOIRE.\n" if obligatoire else "") + aide, "DSI 360")
        note.width = 320
        note.height = 160
        cellule.comment = note
        feuille.column_dimensions[get_column_letter(i)].width = largeur
    feuille.row_dimensions[1].height = 34
    feuille.freeze_panes = "A2"  # l'en-tête reste visible en défilant


def _dropdown_etat(feuille: Worksheet, colonnes: tuple[tuple[str, bool, int, str], ...]) -> None:
    """Liste déroulante Bon / Rebut / Cassé sur la colonne « État constaté »."""
    indices = [i for i, c in enumerate(colonnes, start=1) if c[0] == "État constaté"]
    if not indices:
        return
    lettre = get_column_letter(indices[0])
    validation = DataValidation(
        type="list", formula1='"Bon,Rebut,Cassé"', allow_blank=True,
        showErrorMessage=True, errorTitle="Valeur non prévue",
        error="Choisissez Bon, Rebut ou Cassé — ou laissez vide.",
    )
    feuille.add_data_validation(validation)
    validation.add(f"{lettre}2:{lettre}1000")


def _mode_emploi(feuille: Worksheet) -> None:
    """Feuille d'explications, ignorée par l'import (elle ne porte pas les en-têtes)."""
    feuille.column_dimensions["A"].width = 100
    titre = Font(bold=True, size=14, color=_NOIR)
    soustitre = Font(bold=True, size=11, color=_NOIR)
    fond_titre = PatternFill("solid", fgColor=_VERT_CLAIR)

    lignes: list[tuple[str, Font | None, PatternFill | None]] = [
        ("Modèle d'import de l'inventaire — mode d'emploi", titre, fond_titre),
        ("", None, None),
        ("Comment remplir", soustitre, None),
        ("• Saisissez un équipement par ligne, dans la feuille « Inventaire ».", None, None),
        ("• Seule la colonne « Désignation » est obligatoire. Tout le reste peut rester vide et "
         "sera complété plus tard, à l'écran ou par un prochain import.", None, None),
        ("• Type, Emplacement et Département se créent tout seuls : écrivez-les librement, ils "
         "s'ajoutent au référentiel s'ils n'existent pas encore.", None, None),
        ("• État constaté : choisissez Bon, Rebut ou Cassé (liste déroulante). Laissez vide si le "
         "matériel n'a pas été contrôlé.", None, None),
        ("", None, None),
        ("Création ou mise à jour", soustitre, None),
        ("• Le « Code immo » est la clé. Si le code existe déjà, la ligne MET À JOUR la fiche ; "
         "s'il est nouveau ou vide, elle CRÉE un équipement.", None, None),
        ("• À la mise à jour, les colonnes comptables (désignation, taux, date, durée, valeur) "
         "sont reprises du fichier. Les colonnes de terrain (type, n° série, modèle, emplacement, "
         "département, matricule) ne sont remplies QUE si elles étaient vides : une correction "
         "faite à l'écran n'est jamais écrasée.", None, None),
        ("• Réimporter le même fichier ne crée pas de doublon : la clé « Code immo » l'en empêche.",
         None, None),
        ("", None, None),
        ("Exemple (à recopier dans la feuille « Inventaire », sans cette phrase)", soustitre, None),
        ("Code immo : INV00042  |  Désignation : Ordinateur portable Dell Latitude 5540  |  "
         "Type : Ordinateur portable  |  Matricule : MAT-4507  |  Taux : 25  |  "
         "Date acquisition : 12/03/2024  |  Durée : 4  |  Valeur acquisition : 850000  |  "
         "État constaté : Bon", None, None),
    ]
    for i, (texte, police, fond) in enumerate(lignes, start=1):
        cellule = feuille.cell(row=i, column=1, value=texte)
        cellule.alignment = Alignment(wrap_text=True, vertical="top")
        if police is not None:
            cellule.font = police
        if fond is not None:
            cellule.fill = fond


def construire_modele() -> bytes:
    """Le classeur modèle, en octets .xlsx."""
    classeur = Workbook()
    saisie = classeur.active
    assert saisie is not None  # un classeur neuf a toujours sa feuille active
    saisie.title = "Inventaire"
    _entete(saisie, _COLONNES)
    _dropdown_etat(saisie, _COLONNES)
    _mode_emploi(classeur.create_sheet("Mode d'emploi"))
    tampon = BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()

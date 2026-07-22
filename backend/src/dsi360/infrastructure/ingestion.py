"""Lecture et normalisation du rapport quotidien de tickets (export ServiceDesk .xlsx).

Pur (aucune dépendance base) : transforme le classeur en lignes normalisées, prêtes à être
réconciliées puis upsertées. Le fichier comporte un préambule (filtres) avant la vraie ligne
d'en-têtes ; on la détecte, puis on associe les colonnes par leur intitulé (robuste à l'ordre).
"""

from io import BytesIO
from typing import Any

import openpyxl

from dsi360.infrastructure.classeur import feuille_avec_entetes
from dsi360.infrastructure.classeur import normaliser as _normaliser
from dsi360.infrastructure.classeur import parser_date as _parser_date

# Intitulé d'en-tête (normalisé, sans accents) -> clé canonique. Public : sert aussi à
# reconnaître la nature d'un fichier déposé (cf. routeurs/ingestion).
ENTETES = _ENTETES = {
    "type d'enregistrement de service": "type",
    "statut": "statut",
    "#": "numero",
    "categorie": "categorie",
    "sous-categorie": "sous_categorie",
    "titre": "titre",
    "demandeur": "demandeur",
    "gestionnaire de processus": "gestionnaire",
    "priorite": "priorite",
    "date de la demande": "date_demande",
    "date de fermeture": "date_fermeture",
    "time to repair": "ttr",
    "time to respond": "ttrespond",
}

# Statut brut (normalisé, sans accents) -> issue logique, indépendante du module.
# La table couvre les variantes anglaises ET françaises de l'outil source : un libellé absent
# d'ici retombe sur « ouvert » — et il est SIGNALÉ dans le compte-rendu (statut_inconnu), car un
# repli silencieux laisserait des tickets clos « ouverts » chez nous pour toujours.
_ISSUE = {
    # clôture
    "closed": "cloture",
    "closed - ai": "cloture",
    "verified closed": "cloture",
    "merge closed": "cloture",
    "auto archive": "cloture",
    "auto-closed": "cloture",
    "close email": "cloture",
    "cloture": "cloture",
    "clot": "cloture",
    "ferme": "cloture",
    # résolution
    "request completed": "resolu",
    "resolved": "resolu",
    "completed": "resolu",
    "resolu": "resolu",
    "resolue": "resolu",
    "termine": "resolu",
    "terminee": "resolu",
    # en cours de traitement
    "open": "ouvert",
    "pending": "ouvert",
    "in progress": "ouvert",
    "on hold": "ouvert",
    "assigned": "ouvert",
    "ouvert": "ouvert",
    "ouverte": "ouvert",
    "en cours": "ouvert",
    "en attente": "ouvert",
    "affecte": "ouvert",
    "affectee": "ouvert",
    # nouveau
    "new": "nouveau",
    "nouveau": "nouveau",
    "nouvelle": "nouveau",
    # abandon
    "request rejected": "annule",
    "request cancelled": "annule",
    "request canceled": "annule",
    "cancelled": "annule",
    "canceled": "annule",
    "deleted": "annule",
    "merge deleted": "annule",
    "annule": "annule",
    "annulee": "annule",
    "rejete": "annule",
    "rejetee": "annule",
    "supprime": "annule",
}

# Issue -> état du cycle de vie, par module (cf. domain/etats).
ETAT_PAR_ISSUE = {
    "incident": {
        "nouveau": "Nouveau",
        "ouvert": "Ouvert",
        "resolu": "Résolu",
        "cloture": "Clôturé",
        "annule": "Annulé",
    },
    "demande": {
        "nouveau": "Nouvelle",
        "ouvert": "En cours",
        "resolu": "Résolue",
        "cloture": "Clôturée",
        "annule": "Rejetée",
    },
}


def _parser_duree_minutes(valeur: Any) -> int | None:
    """« 482:53 » (heures:minutes, peut dépasser 24 h) -> minutes."""
    if valeur in (None, ""):
        return None
    texte = str(valeur).strip()
    if ":" not in texte:
        return None
    h, _, m = texte.partition(":")
    try:
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def _parser_priorite(valeur: Any) -> int | None:
    texte = _normaliser(valeur).replace("p", "")
    if texte.isdigit():
        n = int(texte)
        return n if 1 <= n <= 5 else None
    return None


#: Colonnes qui suffisent à reconnaître un rapport de tickets. Public : la détection de la
#: nature d'un fichier déposé s'en sert (cf. routeurs/ingestion) — aucune seconde vérité.
REPERES = {"statut", "titre"}


def analyser_classeur(contenu: bytes) -> list[dict[str, Any]]:
    """Renvoie une liste de tickets normalisés (incident/demande uniquement)."""
    wb = openpyxl.load_workbook(BytesIO(contenu), data_only=True)
    # Les données ne sont pas toujours sur la première feuille (page de filtres, sommaire…).
    lignes, debut, index = feuille_avec_entetes(wb, _ENTETES, REPERES)

    requis = {"type", "statut", "numero", "titre", "priorite", "date_demande"}
    manquant = requis - index.keys()
    if manquant:
        raise ValueError(f"Colonnes manquantes : {', '.join(sorted(manquant))}.")

    def champ(ligne: tuple[Any, ...], cle: str) -> Any:
        j = index.get(cle)
        return ligne[j] if j is not None and j < len(ligne) else None

    tickets: list[dict[str, Any]] = []
    for ligne in lignes[debut + 1 :]:
        type_brut = _normaliser(champ(ligne, "type"))
        if type_brut == "incident":
            module = "incident"
        elif type_brut == "demande":
            module = "demande"
        else:
            continue

        numero = champ(ligne, "numero")
        titre = str(champ(ligne, "titre") or "").strip()
        if numero in (None, "") or titre == "":
            continue

        statut_brut = str(champ(ligne, "statut") or "").strip()
        issue_connue = _ISSUE.get(_normaliser(statut_brut))
        issue = issue_connue or "ouvert"
        statut = ETAT_PAR_ISSUE[module][issue]
        date_demande = _parser_date(champ(ligne, "date_demande"))
        date_fermeture = _parser_date(champ(ligne, "date_fermeture"))

        tickets.append(
            {
                "module": module,
                "source_id": str(numero).strip(),
                "titre": titre[:200],
                "statut": statut,
                "issue": issue,
                # Libellé du fichier hors table : à faire remonter, jamais à taire.
                "statut_inconnu": statut_brut if issue_connue is None and statut_brut else None,
                "priorite": _parser_priorite(champ(ligne, "priorite")),
                "categorie": (str(champ(ligne, "categorie")).strip() if champ(ligne, "categorie") else None),
                "sous_categorie": (
                    str(champ(ligne, "sous_categorie")).strip() if champ(ligne, "sous_categorie") else None
                ),
                "demandeur": (str(champ(ligne, "demandeur")).strip() if champ(ligne, "demandeur") else None),
                "gestionnaire": (
                    str(champ(ligne, "gestionnaire")).strip() if champ(ligne, "gestionnaire") else None
                ),
                "date_demande": date_demande,
                "date_fermeture": date_fermeture,
                "ttr_minutes": _parser_duree_minutes(champ(ligne, "ttr")),
                "ttrespond_minutes": _parser_duree_minutes(champ(ligne, "ttrespond")),
            }
        )
    return tickets

"""Normalisation des saisies libres pour un rendu toujours propre.

- ``nom_propre`` : noms de personnes / éléments → espaces normalisés, initiale de chaque mot
  en majuscule (« awa  toure » → « Awa Toure »).
- ``phrase_propre`` : titres / objets → espaces normalisés, première lettre en majuscule, le
  reste inchangé (« panne du serveur » → « Panne du serveur », acronymes préservés).
- ``nom_significatif`` : un nom réellement renseigné, ou ``None`` — les fichiers importés
  écrivent souvent l'absence (« None », « N/A », « - »…) au lieu de laisser la case vide.
"""

import unicodedata

# Ce qu'un fichier importé écrit quand il n'y a personne. Ce ne sont pas des noms : ce sont des
# absences. Les traiter comme des noms ferait passer le ticket pour pris en charge (par « None »).
_ABSENCES = {
    "",
    "-",
    "--",
    "?",
    "0",
    "inconnu",
    "n/a",
    "na",
    "nan",
    "nil",
    "non affecte",
    "non assigne",
    "non renseigne",
    "non renseignee",
    "none",
    "null",
    "sans",
    "sans objet",
    "unknown",
    "vide",
}


def _condenser(valeur: str) -> str:
    return " ".join(valeur.split())


def nom_significatif(valeur: str | None) -> str | None:
    """Le nom s'il désigne vraiment quelqu'un, sinon ``None`` (absence déguisée en texte)."""
    if valeur is None:
        return None
    base = _condenser(valeur)
    if base == "":
        return None
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFKD", base.lower()) if not unicodedata.combining(c)
    )
    return None if sans_accent in _ABSENCES else base


def nom_propre(valeur: str | None) -> str | None:
    if valeur is None:
        return None
    base = _condenser(valeur)
    return base.title() if base else base


def phrase_propre(valeur: str | None) -> str | None:
    if valeur is None:
        return None
    base = _condenser(valeur)
    return base[:1].upper() + base[1:] if base else base

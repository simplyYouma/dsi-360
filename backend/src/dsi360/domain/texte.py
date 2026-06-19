"""Normalisation des saisies libres pour un rendu toujours propre.

- ``nom_propre`` : noms de personnes / éléments → espaces normalisés, initiale de chaque mot
  en majuscule (« awa  toure » → « Awa Toure »).
- ``phrase_propre`` : titres / objets → espaces normalisés, première lettre en majuscule, le
  reste inchangé (« panne du serveur » → « Panne du serveur », acronymes préservés).
"""


def _condenser(valeur: str) -> str:
    return " ".join(valeur.split())


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

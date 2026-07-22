"""Amortissement linéaire d'une immobilisation — calcul pur, sans dépendance.

C'est le seul vrai calcul métier de l'inventaire : à partir de la valeur d'acquisition, de la date
d'acquisition et du taux, il donne ce que vaut *aujourd'hui* un équipement au bilan.

Convention retenue — **le taux fait foi**. Le fichier porte à la fois un taux (25 %) et une durée
(4 ans), qui disent normalement la même chose (100 / 25 = 4). Quand ils divergent, on calcule sur
le taux, qui est la règle comptable, et on le **signale** (`incoherent`) plutôt que de corriger en
silence : une donnée douteuse doit se voir, pas se maquiller.

Règles :
- l'amortissement cumulé ne dépasse jamais la valeur d'acquisition (VNC plancher à zéro) ;
- sans date d'acquisition ou sans taux, rien n'est calculable : tout est ``None``, et l'écran
  affiche un tiret au lieu d'un chiffre inventé.
"""

from dataclasses import dataclass
from datetime import date

# Un exercice comptable = 365,25 jours (années bissextiles lissées). L'amortissement se calcule
# au prorata temporis : un équipement acquis en juin n'est pas amorti d'une année pleine en
# décembre. Compter en années entières surestimerait la dotation de la première année.
_JOURS_PAR_AN = 365.25


@dataclass(frozen=True)
class Amortissement:
    """Situation d'amortissement d'un équipement à une date donnée."""

    #: Dotation d'une année pleine (valeur × taux).
    dotation_annuelle: float | None
    #: Amorti depuis l'acquisition, plafonné à la valeur d'acquisition.
    cumul: float | None
    #: Valeur nette comptable = valeur d'acquisition − cumul. Jamais négative.
    valeur_nette: float | None
    #: Part amortie, en pourcentage (0 à 100).
    pourcentage: int | None
    #: Date de fin d'amortissement (l'équipement vaut alors zéro au bilan).
    fin: date | None
    #: Plus rien à amortir.
    totalement_amorti: bool
    #: Le taux et la durée du fichier ne disent pas la même chose : donnée à vérifier.
    incoherent: bool


_RIEN = Amortissement(
    dotation_annuelle=None,
    cumul=None,
    valeur_nette=None,
    pourcentage=None,
    fin=None,
    totalement_amorti=False,
    incoherent=False,
)


def calculer(
    valeur_acquisition: float | None,
    date_acquisition: date | None,
    taux: float | None,
    duree_annees: int | None = None,
    *,
    au: date | None = None,
) -> Amortissement:
    """Situation d'amortissement à la date ``au`` (aujourd'hui par défaut).

    Retourne un résultat entièrement vide quand les données ne permettent aucun calcul — mieux
    vaut un tiret à l'écran qu'un chiffre faux.
    """
    if valeur_acquisition is None or date_acquisition is None or not taux or taux <= 0:
        return _RIEN
    if valeur_acquisition < 0:
        return _RIEN

    reference = au or date.today()
    valeur = float(valeur_acquisition)
    taux_annuel = float(taux) / 100.0
    dotation = valeur * taux_annuel

    # Prorata temporis, borné à zéro : un équipement acquis dans le futur n'est pas encore amorti.
    annees = max(0.0, (reference - date_acquisition).days / _JOURS_PAR_AN)
    cumul = min(valeur, dotation * annees)
    nette = valeur - cumul

    duree_theorique = 100.0 / float(taux)
    fin = date.fromordinal(
        date_acquisition.toordinal() + round(duree_theorique * _JOURS_PAR_AN)
    )
    # Écart d'au moins une demi-année entre la durée annoncée et celle qu'implique le taux.
    incoherent = duree_annees is not None and abs(duree_theorique - duree_annees) >= 0.5

    return Amortissement(
        dotation_annuelle=round(dotation, 2),
        cumul=round(cumul, 2),
        valeur_nette=round(nette, 2),
        pourcentage=round(cumul * 100 / valeur) if valeur else 0,
        fin=fin,
        totalement_amorti=nette <= 0,
        incoherent=incoherent,
    )

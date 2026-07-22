"""Traduction des phases du domaine en condition SQL.

Filtres de liste, compteurs, analyses, rappels d'échéance : tous ont besoin de dire « ce dossier
est-il encore en cours ? ». La réponse vient de `domain.etats`, jamais d'une liste de statuts
écrite à la main — et jamais des horodatages : seuls « Résolu » et « Clôturé » posent un
`resolu_le` / `cloture_le`. « Réalisé », « Rejeté », « Maîtrisé » n'en posent aucun, et se
faisaient donc passer pour des dossiers vivants.
"""

from dsi360.domain import etats


def condition(
    *phases: str, colonne: str = "a.statut", modules: tuple[str, ...] | None = None
) -> str:
    """Condition « le statut appartient à ces phases ».

    ``modules`` restreint aux statuts de ces modules ; sinon tous, ce qui est sans risque : un
    même libellé porte partout la même phase (garanti par les tests du domaine).
    """
    if modules is None:
        noms = sorted(etats.statuts_de_phase(*phases))
    else:
        noms = sorted({s for m in modules for s in etats.statuts_de_phase(*phases, module=m)})
    if not noms:
        # Aucun statut dans cette phase pour ce module : la condition est franchement fausse
        # plutôt que vide, sinon elle laisserait tout passer.
        return "false"
    valeurs = ", ".join("'" + n.replace("'", "''") + "'" for n in noms)
    return f"{colonne} IN ({valeurs})"


def en_cours(colonne: str = "a.statut", modules: tuple[str, ...] | None = None) -> str:
    """Le dossier réclame encore du travail — la seule population qui peut être « en retard »."""
    return condition(etats.EN_COURS, colonne=colonne, modules=modules)

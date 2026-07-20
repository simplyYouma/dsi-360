"""Cohérence de la table des états : c'est la source de vérité, elle doit se tenir.

Ces tests ne vérifient pas un comportement d'écran mais l'intégrité de la déclaration elle-même.
Ils empêchent qu'un ajout de statut réintroduise les incohérences qu'on vient de supprimer.
"""

import pytest

from dsi360.domain.etats import (
    ABANDONNE,
    EN_COURS,
    ETATS,
    PHASES_FINIES,
    TERMINE,
    est_etat_terminal,
    etat_initial,
    ordre_etats,
    phase,
    statuts_de_phase,
    transitions_possibles,
)

PHASES = {EN_COURS, TERMINE, ABANDONNE}
TONS = {"nouveau", "actif", "attente", "recul", "succes", "echec"}


@pytest.mark.parametrize("module", sorted(ETATS))
def test_chaque_suite_pointe_vers_un_etat_declare(module: str) -> None:
    """Aucune transition ne mène nulle part : sinon le workflow casse à l'exécution."""
    connus = set(ETATS[module])
    for nom, etat in ETATS[module].items():
        for suite in etat.suites:
            assert suite in connus, f"{module}.{nom} mène à « {suite} », qui n'existe pas"


@pytest.mark.parametrize("module", sorted(ETATS))
def test_phases_et_tons_appartiennent_au_vocabulaire(module: str) -> None:
    """Le vocabulaire est fermé : une faute de frappe rangerait le statut n'importe où."""
    for nom, etat in ETATS[module].items():
        assert etat.phase in PHASES, f"{module}.{nom} : phase « {etat.phase} » inconnue"
        assert etat.ton in TONS, f"{module}.{nom} : ton « {etat.ton} » inconnu"


@pytest.mark.parametrize("module", sorted(ETATS))
def test_un_etat_sans_suite_est_forcement_fini(module: str) -> None:
    """Le verrou et la phase peuvent différer, mais pas se contredire.

    Un état sans suite est définitivement clos : le classer « en cours » laisserait le dossier
    dans les listes actives sans qu'aucune action ne puisse jamais l'en sortir.
    """
    for nom in etats_sans_suite(module):
        assert phase(module, nom) in PHASES_FINIES, (
            f"{module}.{nom} n'a aucune suite mais reste en phase « en cours » : impasse"
        )


def etats_sans_suite(module: str) -> list[str]:
    return [nom for nom, e in ETATS[module].items() if not e.suites]


@pytest.mark.parametrize("module", sorted(ETATS))
def test_le_premier_etat_est_le_point_d_entree(module: str) -> None:
    """L'ordre de déclaration porte le cycle de vie : le premier état doit être celui d'arrivée."""
    depart = etat_initial(module)
    assert depart == ordre_etats(module)[0]
    cibles = {s for nom in ETATS[module] for s in transitions_possibles(module, nom)}
    assert depart not in cibles, f"{module} : on revient sur « {depart} », ce n'est pas un départ"


@pytest.mark.parametrize("module", sorted(ETATS))
def test_chaque_module_peut_aboutir(module: str) -> None:
    """Un module dont aucun statut n'est « terminé » afficherait un compteur vide à jamais."""
    assert statuts_de_phase(TERMINE, module=module), f"{module} : aucun état d'aboutissement"


@pytest.mark.parametrize("attribut", ["phase", "ton"])
def test_un_meme_libelle_garde_le_meme_sens_partout(attribut: str) -> None:
    """Un statut homonyme doit signifier la même chose dans tous les modules.

    Sinon les statistiques transverses mentiraient — et l'écran, qui affiche souvent un badge sans
    connaître le module (listes mêlées, « Ses tickets »), n'aurait aucun moyen de trancher.
    """
    vu: dict[str, tuple[str, str]] = {}
    for module, etats in ETATS.items():
        for nom, etat in etats.items():
            valeur = getattr(etat, attribut)
            if nom in vu:
                autre_module, autre_valeur = vu[nom]
                assert valeur == autre_valeur, (
                    f"« {nom} » a {attribut}={valeur} dans {module} "
                    f"mais {autre_valeur} dans {autre_module}"
                )
            else:
                vu[nom] = (module, valeur)


def test_resolu_est_termine_sans_etre_verrouille() -> None:
    """Le cas qui justifie de garder deux notions distinctes."""
    assert phase("incident", "Résolu") == TERMINE, "il ne compte plus comme en cours"
    assert not est_etat_terminal("incident", "Résolu"), "mais il reste clôturable et réouvrable"


def test_un_risque_maitrise_ne_compte_plus_comme_en_cours() -> None:
    """Décision métier : le risque quitte les listes actives, sa revue périodique l'y ramènera."""
    assert phase("risque", "Maîtrisé") == TERMINE
    assert phase("risque", "Accepté") == TERMINE
    assert phase("risque", "Traitement") == EN_COURS


def test_un_changement_implemente_reste_en_cours() -> None:
    """La revue post-implémentation est obligatoire : le changement n'est pas fini avant elle."""
    assert phase("changement", "Implémenté") == EN_COURS
    assert phase("changement", "Validé") == EN_COURS, "six étapes restent après le CAB"
    assert phase("changement", "Clôturé") == TERMINE


def test_un_statut_inconnu_est_traite_comme_en_cours() -> None:
    """Prudence : on ne range jamais d'office un dossier parmi les affaires réglées."""
    assert phase("incident", "Inventé") == EN_COURS
    assert phase("module-inconnu", "Ouvert") == EN_COURS

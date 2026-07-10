"""Règles d'autorisation par activité — l'admin distribue, les acteurs exécutent.

Cf. le tableau de capacités : ADMIN organise (assigner, évaluer, désigner) ; le responsable et les
contributeurs travaillent ; le valideur ne fait que décider ; l'assigné d'une tâche n'en change que
le statut ; le lecteur regarde.

Fonctions pures : aucune base, aucun HTTP.
"""

import pytest

from dsi360.application.autorisations import (
    ACTEUR,
    ADMIN,
    VALIDEUR,
    RolesActivite,
    capacites,
    controler_champs_tache,
    satisfait,
    visible,
)

LECTEUR = RolesActivite()
ADMINISTRATEUR = RolesActivite(est_admin=True)
RESPONSABLE = RolesActivite(est_responsable=True)
CONTRIBUTEUR = RolesActivite(est_contributeur=True)
LE_VALIDEUR = RolesActivite(est_valideur=True)
ASSIGNE = RolesActivite(est_assigne=True)


# --- Acteur de travail ---------------------------------------------------------------------------


@pytest.mark.parametrize("roles", [ADMINISTRATEUR, RESPONSABLE, CONTRIBUTEUR])
def test_acteurs_de_travail(roles: RolesActivite) -> None:
    assert roles.est_acteur_travail


@pytest.mark.parametrize("roles", [LECTEUR, LE_VALIDEUR, ASSIGNE])
def test_ne_sont_pas_acteurs_de_travail(roles: RolesActivite) -> None:
    assert not roles.est_acteur_travail


def test_un_valideur_aussi_contributeur_travaille() -> None:
    assert RolesActivite(est_valideur=True, est_contributeur=True).est_acteur_travail


# --- Capacités -----------------------------------------------------------------------------------


def test_l_administrateur_organise_et_travaille_mais_ne_decide_pas() -> None:
    """Séparation des tâches : l'admin ne valide pas à la place des valideurs."""
    c = capacites(ADMINISTRATEUR)

    assert c["peut_assigner"] and c["peut_evaluer"] and c["peut_gerer_acteurs"]
    assert c["peut_travailler"]
    assert not c["peut_decider"]


@pytest.mark.parametrize("roles", [RESPONSABLE, CONTRIBUTEUR])
def test_les_acteurs_travaillent_mais_n_organisent_pas(roles: RolesActivite) -> None:
    c = capacites(roles)

    assert c["peut_travailler"]
    assert not c["peut_assigner"], "changer le gestionnaire reste à l'admin"
    assert not c["peut_evaluer"], "impact/urgence et le Type restent à l'admin"
    assert not c["peut_gerer_acteurs"], "désigner reste à l'admin"


def test_le_valideur_ne_fait_que_decider() -> None:
    c = capacites(LE_VALIDEUR)

    assert c["peut_decider"]
    assert not c["peut_travailler"]
    assert not any(c[cle] for cle in ("peut_assigner", "peut_evaluer", "peut_gerer_acteurs"))


def test_le_lecteur_ne_peut_rien() -> None:
    assert not any(capacites(LECTEUR).values())


def test_un_admin_valideur_peut_decider() -> None:
    assert capacites(RolesActivite(est_admin=True, est_valideur=True))["peut_decider"]


def test_sur_un_module_importe_le_lecteur_travaille() -> None:
    """Incidents et demandes : un ticket sans gestionnaire n'aurait sinon aucun acteur."""
    c = capacites(LECTEUR, travail_ouvert=True)

    assert c["peut_travailler"]
    assert not c["peut_assigner"], "assigner reste à l'admin, même sur un ticket importé"


# --- Satisfaction d'une exigence -----------------------------------------------------------------


def test_exigence_admin() -> None:
    assert satisfait(ADMINISTRATEUR, {ADMIN})
    assert not satisfait(RESPONSABLE, {ADMIN})
    assert not satisfait(CONTRIBUTEUR, {ADMIN})


def test_exigence_acteur() -> None:
    for roles in (ADMINISTRATEUR, RESPONSABLE, CONTRIBUTEUR):
        assert satisfait(roles, {ACTEUR})
    for roles in (LECTEUR, LE_VALIDEUR, ASSIGNE):
        assert not satisfait(roles, {ACTEUR})


def test_exigence_valideur() -> None:
    assert satisfait(LE_VALIDEUR, {VALIDEUR})
    assert not satisfait(ADMINISTRATEUR, {VALIDEUR}), "l'admin ne décide pas à leur place"


def test_exigence_multiple_est_un_ou() -> None:
    assert satisfait(LE_VALIDEUR, {ACTEUR, VALIDEUR})
    assert satisfait(CONTRIBUTEUR, {ACTEUR, VALIDEUR})
    assert not satisfait(LECTEUR, {ACTEUR, VALIDEUR})


# --- Visibilité ----------------------------------------------------------------------------------

TRANSVERSE = {"transverse": True, "direction": "DSI"}
AGENT_DSI = {"transverse": False, "direction": "DSI"}


def test_un_transverse_voit_tout() -> None:
    assert visible("AUTRE", TRANSVERSE, LECTEUR)


def test_on_voit_sa_direction_et_les_activites_sans_direction() -> None:
    assert visible("DSI", AGENT_DSI, LECTEUR)
    assert visible(None, AGENT_DSI, LECTEUR)


def test_on_ne_voit_pas_une_autre_direction() -> None:
    assert not visible("AUTRE", AGENT_DSI, LECTEUR)


@pytest.mark.parametrize("roles", [RESPONSABLE, CONTRIBUTEUR, LE_VALIDEUR, ASSIGNE])
def test_un_acteur_designe_voit_hors_de_sa_direction(roles: RolesActivite) -> None:
    """Être désigné donne accès : sinon la désignation serait lettre morte."""
    assert visible("AUTRE", AGENT_DSI, roles)


# --- Champs d'une tâche --------------------------------------------------------------------------


@pytest.mark.parametrize("roles", [ADMINISTRATEUR, RESPONSABLE, CONTRIBUTEUR])
def test_un_acteur_de_travail_modifie_tous_les_champs(roles: RolesActivite) -> None:
    champs = {"titre", "echeance"}

    assert controler_champs_tache(roles, assigne_de_la_tache=False, champs=champs) is None


def test_l_assigne_ne_change_que_le_statut_de_sa_tache() -> None:
    assert controler_champs_tache(LECTEUR, assigne_de_la_tache=True, champs={"statut"}) is None


@pytest.mark.parametrize("champ", ["assigne_id", "echeance", "titre", "ordre"])
def test_l_assigne_ne_touche_pas_aux_autres_champs(champ: str) -> None:
    message = controler_champs_tache(LECTEUR, assigne_de_la_tache=True, champs={champ})

    assert message is not None and "statut" in message


def test_un_tiers_ne_touche_a_rien() -> None:
    message = controler_champs_tache(LECTEUR, assigne_de_la_tache=False, champs={"statut"})

    assert message is not None


def test_l_assigne_qui_est_aussi_contributeur_modifie_tout() -> None:
    assert (
        controler_champs_tache(CONTRIBUTEUR, assigne_de_la_tache=True, champs={"echeance"}) is None
    )

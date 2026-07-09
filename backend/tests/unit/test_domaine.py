from datetime import UTC, date, datetime, timedelta

import pytest

from dsi360.domain.activite import calculer_criticite, calculer_priorite
from dsi360.domain.changement import dossier_incomplet_pour
from dsi360.domain.etats import (
    cible_apres_decisions,
    etat_initial,
    etats_terminaux,
    ordre_etats,
    transition_autorisee,
    transition_reservee,
    transitions_possibles,
)
from dsi360.domain.revue import prochaine_revue
from dsi360.domain.sla import echeances, statut_sla


class TestPriorite:
    def test_max_donne_p1(self) -> None:
        assert calculer_priorite(impact=5, urgence=5) == 1

    def test_min_donne_p5(self) -> None:
        assert calculer_priorite(impact=1, urgence=1) == 5

    def test_intermediaire(self) -> None:
        assert calculer_priorite(impact=5, urgence=1) == 3
        assert calculer_priorite(impact=3, urgence=3) == 3

    def test_hors_bornes(self) -> None:
        with pytest.raises(ValueError):
            calculer_priorite(impact=0, urgence=3)
        with pytest.raises(ValueError):
            calculer_priorite(impact=3, urgence=6)


class TestCriticite:
    def test_extremes(self) -> None:
        assert calculer_criticite(probabilite=5, impact=5) == 5
        assert calculer_criticite(probabilite=1, impact=1) == 1


class TestEtats:
    def test_etat_initial(self) -> None:
        assert etat_initial("incident") == "Nouveau"
        assert etat_initial("changement") == "Brouillon"

    def test_transition_valide(self) -> None:
        assert transition_autorisee("incident", "Nouveau", "Ouvert") is True
        assert transition_autorisee("changement", "Évaluation", "CAB") is True

    def test_transition_invalide(self) -> None:
        assert transition_autorisee("incident", "Nouveau", "Clôturé") is False

    def test_module_inconnu(self) -> None:
        with pytest.raises(ValueError):
            transitions_possibles("inexistant", "X")

    def test_nouveaux_modules(self) -> None:
        assert etat_initial("cybersecurite") == "Ouvert"
        assert etat_initial("gouvernance") == "À engager"
        assert transition_autorisee("cybersecurite", "Ouvert", "En traitement") is True
        assert transition_autorisee("gouvernance", "À engager", "En cours") is True
        assert transition_autorisee("gouvernance", "À engager", "Réalisé") is False

    def test_ordre_etats(self) -> None:
        ordre = ordre_etats("incident")
        assert ordre[0] == "Nouveau"
        assert "Clôturé" in ordre

    def test_etats_terminaux(self) -> None:
        # États sans suite possible : « Mes tickets » s'en sert pour sortir les cartes mortes.
        assert etats_terminaux("incident") == ["Annulé"]
        assert etats_terminaux("demande") == ["Rejetée"]
        assert "Rejeté" in etats_terminaux("changement")
        assert etats_terminaux("gouvernance") == ["Réalisé"]
        # « Résolu » n'est PAS terminal (il reste à clôturer) : encore en file active.
        assert "Résolu" not in etats_terminaux("incident")

    def test_etats_terminaux_module_inconnu(self) -> None:
        with pytest.raises(ValueError):
            etats_terminaux("inexistant")


class TestDecisionsValideurs:
    def test_approbation_unanime_change_valide(self) -> None:
        assert cible_apres_decisions("changement", "CAB", ["APPROUVE", "APPROUVE"]) == "Validé"
        assert cible_apres_decisions("changement", "ECAB", ["APPROUVE"]) == "Validé"

    def test_un_rejet_rejette(self) -> None:
        assert cible_apres_decisions("changement", "CAB", ["APPROUVE", "REJETE"]) == "Rejeté"

    def test_decision_en_attente_ne_bascule_pas(self) -> None:
        assert cible_apres_decisions("changement", "CAB", ["APPROUVE", None]) is None

    def test_sans_valideur_ne_bascule_pas(self) -> None:
        assert cible_apres_decisions("changement", "CAB", []) is None

    def test_hors_etat_attente_ne_bascule_pas(self) -> None:
        assert cible_apres_decisions("changement", "Planifié", ["APPROUVE"]) is None

    def test_demande_validation(self) -> None:
        assert cible_apres_decisions("demande", "En validation", ["APPROUVE"]) == "Résolue"
        assert cible_apres_decisions("demande", "En validation", ["REJETE"]) == "Rejetée"

    def test_module_sans_porte(self) -> None:
        assert cible_apres_decisions("incident", "Ouvert", ["APPROUVE"]) is None


class TestTransitionReservee:
    def test_issue_validation_reservee(self) -> None:
        # Pousser « Validé » depuis CAB à la main est réservé (doit passer par les valideurs).
        assert transition_reservee("changement", "CAB", "Validé") is True
        assert transition_reservee("changement", "ECAB", "Rejeté") is True
        assert transition_reservee("demande", "En validation", "Résolue") is True

    def test_transition_ordinaire_non_reservee(self) -> None:
        assert transition_reservee("changement", "Validé", "Planifié") is False
        assert transition_reservee("incident", "Nouveau", "Ouvert") is False

    def test_module_sans_porte(self) -> None:
        assert transition_reservee("incident", "Ouvert", "Résolu") is False


class TestSla:
    def test_echeances_p1(self) -> None:
        debut = datetime(2026, 6, 17, 8, 0, tzinfo=UTC)
        ech = echeances(priorite=1, debut=debut)
        assert ech.prise_en_charge_le == debut + timedelta(minutes=15)
        assert ech.resolution_le == debut + timedelta(hours=4)

    def test_statut_depasse(self) -> None:
        ech = datetime(2026, 6, 17, 8, 0, tzinfo=UTC)
        maintenant = datetime(2026, 6, 17, 9, 0, tzinfo=UTC)
        assert statut_sla(ech, maintenant, timedelta(minutes=30)) == "depasse"

    def test_statut_approche(self) -> None:
        ech = datetime(2026, 6, 17, 9, 0, tzinfo=UTC)
        maintenant = datetime(2026, 6, 17, 8, 45, tzinfo=UTC)
        assert statut_sla(ech, maintenant, timedelta(minutes=30)) == "approche"

    def test_statut_a_lheure(self) -> None:
        ech = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
        maintenant = datetime(2026, 6, 17, 8, 0, tzinfo=UTC)
        assert statut_sla(ech, maintenant, timedelta(minutes=30)) == "a_lheure"


class TestRevuePeriodique:
    def test_cadence_par_periodicite(self) -> None:
        depart = date(2026, 1, 15)
        assert prochaine_revue("Mensuelle", depart) == date(2026, 2, 15)
        assert prochaine_revue("Trimestrielle", depart) == date(2026, 4, 15)
        assert prochaine_revue("Semestrielle", depart) == date(2026, 7, 15)
        assert prochaine_revue("Annuelle", depart) == date(2027, 1, 15)

    def test_borne_le_jour_au_dernier_du_mois(self) -> None:
        # 31 janvier + 1 mois -> 28 février (2026 n'est pas bissextile), pas de date invalide.
        assert prochaine_revue("Mensuelle", date(2026, 1, 31)) == date(2026, 2, 28)
        # Année bissextile : 29 février existe.
        assert prochaine_revue("Mensuelle", date(2024, 1, 31)) == date(2024, 2, 29)

    def test_franchit_l_annee(self) -> None:
        assert prochaine_revue("Trimestrielle", date(2026, 11, 30)) == date(2027, 2, 28)

    def test_periodicite_inconnue(self) -> None:
        with pytest.raises(ValueError):
            prochaine_revue("Hebdomadaire", date(2026, 1, 1))


class TestDossierRfc:
    _COMPLET = {
        "analyse_impact": "Core banking et agences.",
        "analyse_risque": "Régression maîtrisée.",
        "plan_retour_arriere": "Restauration N-1.",
    }

    def test_dossier_complet_passe(self) -> None:
        assert dossier_incomplet_pour("changement", "CAB", self._COMPLET) == []

    def test_dossier_vide_bloque_le_comite(self) -> None:
        manquantes = dossier_incomplet_pour("changement", "CAB", {})
        assert manquantes == [
            "l'analyse d'impact",
            "l'analyse de risque",
            "le plan de retour arrière",
        ]

    def test_ecab_soumis_au_meme_controle(self) -> None:
        assert dossier_incomplet_pour("changement", "ECAB", {}) != []

    def test_champ_blanc_compte_comme_manquant(self) -> None:
        donnees = {**self._COMPLET, "plan_retour_arriere": "   "}
        assert dossier_incomplet_pour("changement", "CAB", donnees) == [
            "le plan de retour arrière"
        ]

    def test_le_plan_de_deploiement_n_est_pas_exige(self) -> None:
        # Il est utile mais n'est pas une pièce d'instruction du comité (SI-12.04).
        assert dossier_incomplet_pour("changement", "CAB", self._COMPLET) == []

    def test_autres_transitions_non_concernees(self) -> None:
        assert dossier_incomplet_pour("changement", "Planifié", {}) == []

    def test_autres_modules_non_concernes(self) -> None:
        assert dossier_incomplet_pour("demande", "CAB", {}) == []

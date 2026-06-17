from datetime import datetime, timedelta, timezone

import pytest

from dsi360.domain.activite import calculer_criticite, calculer_priorite
from dsi360.domain.etats import etat_initial, transition_autorisee, transitions_possibles
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


class TestSla:
    def test_echeances_p1(self) -> None:
        debut = datetime(2026, 6, 17, 8, 0, tzinfo=timezone.utc)
        ech = echeances(priorite=1, debut=debut)
        assert ech.prise_en_charge_le == debut + timedelta(minutes=15)
        assert ech.resolution_le == debut + timedelta(hours=4)

    def test_statut_depasse(self) -> None:
        ech = datetime(2026, 6, 17, 8, 0, tzinfo=timezone.utc)
        maintenant = datetime(2026, 6, 17, 9, 0, tzinfo=timezone.utc)
        assert statut_sla(ech, maintenant, timedelta(minutes=30)) == "depasse"

    def test_statut_approche(self) -> None:
        ech = datetime(2026, 6, 17, 9, 0, tzinfo=timezone.utc)
        maintenant = datetime(2026, 6, 17, 8, 45, tzinfo=timezone.utc)
        assert statut_sla(ech, maintenant, timedelta(minutes=30)) == "approche"

    def test_statut_a_lheure(self) -> None:
        ech = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
        maintenant = datetime(2026, 6, 17, 8, 0, tzinfo=timezone.utc)
        assert statut_sla(ech, maintenant, timedelta(minutes=30)) == "a_lheure"

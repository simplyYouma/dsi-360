"""Amortissement : le calcul qui porte la valeur du parc au bilan.

C'est ici que se logent les erreurs coûteuses — une VNC fausse, et tout le module ment. Ces tests
couvrent le cycle complet d'un équipement, plus les données incomplètes que le fichier contient
forcément.
"""

from datetime import date

import pytest

from dsi360.domain.amortissement import calculer

# Le GAB de l'échantillon : 23 074 595 FCFA, acquis le 22/07/2005, 25 % sur 4 ans.
_VALEUR = 23_074_595.0
_ACHAT = date(2005, 7, 22)
_TAUX = 25.0


class TestCycleDeVie:
    def test_un_equipement_neuf_vaut_son_prix(self) -> None:
        a = calculer(_VALEUR, _ACHAT, _TAUX, 4, au=_ACHAT)
        assert a.cumul == 0
        assert a.valeur_nette == _VALEUR
        assert a.pourcentage == 0
        assert not a.totalement_amorti

    def test_apres_un_an_un_quart_est_amorti(self) -> None:
        a = calculer(_VALEUR, _ACHAT, _TAUX, 4, au=date(2006, 7, 22))
        assert a.dotation_annuelle == pytest.approx(_VALEUR * 0.25, rel=1e-6)
        assert a.pourcentage == 25
        assert a.valeur_nette == pytest.approx(_VALEUR * 0.75, rel=1e-3)

    def test_a_mi_vie_la_moitie_reste(self) -> None:
        a = calculer(_VALEUR, _ACHAT, _TAUX, 4, au=date(2007, 7, 22))
        assert a.pourcentage == 50
        assert not a.totalement_amorti

    def test_au_terme_la_valeur_nette_est_nulle(self) -> None:
        a = calculer(_VALEUR, _ACHAT, _TAUX, 4, au=date(2009, 7, 22))
        assert a.valeur_nette == 0
        assert a.totalement_amorti
        assert a.pourcentage == 100

    def test_bien_apres_le_terme_la_valeur_ne_devient_jamais_negative(self) -> None:
        """Un GAB de 2005 est amorti depuis vingt ans : le bilan ne descend pas sous zéro."""
        a = calculer(_VALEUR, _ACHAT, _TAUX, 4, au=date(2026, 7, 22))
        assert a.valeur_nette == 0
        assert a.cumul == _VALEUR, "le cumul est plafonné à la valeur d'acquisition"
        assert a.pourcentage == 100
        assert a.totalement_amorti

    def test_la_date_de_fin_suit_le_taux(self) -> None:
        a = calculer(_VALEUR, _ACHAT, _TAUX, 4)
        assert a.fin is not None
        assert a.fin.year == 2009, "25 % par an = quatre ans"


class TestProrataTemporis:
    def test_une_acquisition_recente_n_est_amortie_qu_au_prorata(self) -> None:
        """Compter en années entières surestimerait la dotation de la première année."""
        a = calculer(1000.0, date(2026, 1, 1), 25.0, 4, au=date(2026, 7, 1))
        assert a.pourcentage == 12, "six mois à 25 %/an ≈ 12,5 %"

    def test_une_acquisition_a_venir_n_est_pas_encore_amortie(self) -> None:
        """Une date d'acquisition postérieure ne doit pas produire un amortissement négatif."""
        a = calculer(1000.0, date(2027, 1, 1), 25.0, 4, au=date(2026, 1, 1))
        assert a.cumul == 0
        assert a.valeur_nette == 1000.0


class TestDonneesIncompletes:
    """Le fichier comporte des lignes trouées : mieux vaut un tiret qu'un chiffre inventé."""

    @pytest.mark.parametrize(
        ("valeur", "achat", "taux"),
        [
            (None, _ACHAT, _TAUX),  # pas de valeur d'acquisition
            (_VALEUR, None, _TAUX),  # pas de date d'acquisition
            (_VALEUR, _ACHAT, None),  # pas de taux
            (_VALEUR, _ACHAT, 0.0),  # taux nul : on ne divise pas par zéro
            (-5.0, _ACHAT, _TAUX),  # valeur aberrante
        ],
    )
    def test_sans_les_elements_necessaires_rien_n_est_calcule(
        self, valeur: float | None, achat: date | None, taux: float | None
    ) -> None:
        a = calculer(valeur, achat, taux, 4)
        assert a.valeur_nette is None
        assert a.cumul is None
        assert a.pourcentage is None
        assert a.fin is None
        assert not a.totalement_amorti


class TestCoherenceTauxDuree:
    """Le fichier porte taux ET durée : ils doivent dire la même chose."""

    def test_un_taux_coherent_avec_la_duree_ne_signale_rien(self) -> None:
        assert not calculer(_VALEUR, _ACHAT, 25.0, 4).incoherent
        assert not calculer(_VALEUR, _ACHAT, 20.0, 5).incoherent

    def test_une_divergence_est_signalee_sans_etre_corrigee(self) -> None:
        """25 % sur 10 ans est contradictoire : on le dit, et on calcule sur le taux."""
        a = calculer(1000.0, date(2020, 1, 1), 25.0, 10, au=date(2021, 1, 1))
        assert a.incoherent
        assert a.pourcentage == 25, "le taux fait foi, pas la durée annoncée"

    def test_sans_duree_annoncee_il_n_y_a_rien_a_contredire(self) -> None:
        assert not calculer(_VALEUR, _ACHAT, 25.0, None).incoherent

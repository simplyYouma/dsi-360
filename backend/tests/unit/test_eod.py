"""Règles de l'EOD : ce que les étapes disent de la soirée, et ce qu'on refuse de laisser passer.

Ces tests portent sur les fonctions pures (domaine + cas d'usage sans base). Ils fixent les
décisions qui, prises à l'envers, feraient mentir le rapport du soir.
"""

from datetime import UTC, datetime

import pytest

from dsi360.application.eod import (
    cloture_conseillee,
    etat_de_la_nuit,
    justification_manquante,
    pointage,
    titre_journee,
)
from dsi360.domain.activite import CHEMIN_MODULE, MODULES, PREFIXE_REFERENCE, lien_activite
from dsi360.domain.eod import (
    A_FAIRE,
    ANOMALIE,
    COMPLETE,
    DEROULE_REFERENCE,
    EN_COURS,
    NON_APPLICABLE,
    SECTIONS,
    avancement,
    compter_anomalies,
    ordre_section,
    reste_a_faire,
)
from dsi360.domain.etats import ETATS, est_etat_terminal, etat_initial, phase


class TestDerouleDeReference:
    """Le déroulé relevé sur le rapport réel d'AFG Bank Mali (soirée du 15/09/2026)."""

    def test_les_vingt_huit_etapes_de_la_soiree(self) -> None:
        assert len(DEROULE_REFERENCE) == 28

    def test_chaque_etape_appartient_a_une_section_connue(self) -> None:
        for etape in DEROULE_REFERENCE:
            assert etape.section in SECTIONS, etape.libelle

    def test_la_date_systeme_est_relevee_avant_et_apres_la_bascule(self) -> None:
        """C'est la vérification qui dit si l'EOD a réellement fait basculer la journée."""
        dates = [e for e in DEROULE_REFERENCE if e.libelle == "System Date"]
        assert len(dates) == 2
        assert {e.nature for e in dates} == {"valeur"}
        assert dates[0].section == "Préparation"
        assert dates[1].section == "Tâches additionnelles"

    def test_les_quatre_parts_de_l_eod_sont_dans_l_ordre(self) -> None:
        """Chaque PART suppose la précédente faite : leur ordre n'est pas décoratif."""
        parts = [e.section for e in DEROULE_REFERENCE if e.section.startswith("PART")]
        assert parts == ["PART 1", "PART 2", "PART 3", "PART 4"]

    def test_une_section_inconnue_se_range_en_fin_de_liste(self) -> None:
        """Une étape ajoutée à la main ne doit pas s'intercaler au milieu du déroulé."""
        assert ordre_section("Préparation") == 0
        assert ordre_section("Opération exceptionnelle") == len(SECTIONS)


class TestEtatDeLaNuit:
    def test_une_soiree_vierge_n_est_pas_commencee(self) -> None:
        assert avancement([A_FAIRE] * 28) == 0
        assert reste_a_faire([A_FAIRE] * 28) == 28

    def test_le_non_applicable_compte_comme_regle(self) -> None:
        """Un soir sans fin de mois n'est pas un soir à 96 % : l'étape EOM ne s'appliquait pas."""
        statuts = [COMPLETE] * 27 + [NON_APPLICABLE]
        assert avancement(statuts) == 100
        assert reste_a_faire(statuts) == 0

    def test_une_anomalie_regle_l_etape_sans_l_effacer(self) -> None:
        """L'étape ne sera plus attendue ce soir, mais elle reste comptée comme anomalie."""
        statuts = [COMPLETE] * 27 + [ANOMALIE]
        assert reste_a_faire(statuts) == 0
        assert compter_anomalies(statuts) == 1

    def test_une_etape_en_cours_reste_a_faire(self) -> None:
        assert reste_a_faire([COMPLETE, EN_COURS]) == 1

    def test_une_soiree_sans_etape_n_affiche_pas_cent_pour_cent(self) -> None:
        """Le piège du 0/0 : une division vide ne doit pas déclarer la nuit terminée."""
        assert avancement([]) == 0

    def test_l_etat_resume_la_nuit_en_quatre_chiffres(self) -> None:
        etat = etat_de_la_nuit([COMPLETE, COMPLETE, ANOMALIE, A_FAIRE])
        assert etat == {"avancement": 75, "reste": 1, "anomalies": 1, "etapes": 4}


class TestClotureConseillee:
    def test_rien_n_est_conseille_tant_qu_une_etape_traine(self) -> None:
        assert cloture_conseillee([COMPLETE, A_FAIRE]) is None

    def test_une_nuit_sans_accroc_se_clot_simplement(self) -> None:
        assert cloture_conseillee([COMPLETE, NON_APPLICABLE]) == "Clôturé"

    def test_une_anomalie_impose_la_mention_des_reserves(self) -> None:
        """Proposer « Clôturé » sur une nuit qui porte une anomalie inviterait à l'effacer."""
        assert cloture_conseillee([COMPLETE, ANOMALIE]) == "Clôturé avec réserves"


class TestPointage:
    _MAINTENANT = datetime(2026, 9, 15, 20, 29, tzinfo=UTC)

    def test_demarrer_horodate_et_fait_avancer_le_statut(self) -> None:
        """Un seul geste : sinon on obtient des étapes horodatées restées « À faire »."""
        fixes = pointage("debut", {"debut": None, "statut": A_FAIRE}, self._MAINTENANT)
        assert fixes == {"debut": self._MAINTENANT, "statut": EN_COURS}

    def test_terminer_pose_la_fin_et_complete_l_etape(self) -> None:
        fixes = pointage("fin", {"debut": self._MAINTENANT, "statut": EN_COURS}, self._MAINTENANT)
        assert fixes == {"fin": self._MAINTENANT, "statut": COMPLETE}

    def test_terminer_une_etape_jamais_demarree_ne_laisse_pas_de_trou(self) -> None:
        """L'opérateur qui rattrape une ligne oubliée ne doit pas avoir à inventer une heure."""
        fixes = pointage("fin", {"debut": None, "statut": A_FAIRE}, self._MAINTENANT)
        assert fixes["debut"] == self._MAINTENANT
        assert fixes["fin"] == self._MAINTENANT


class TestJustification:
    @pytest.mark.parametrize("statut", [ANOMALIE, NON_APPLICABLE])
    def test_un_verdict_qui_sort_de_l_ordinaire_s_explique(self, statut: str) -> None:
        """Six semaines plus tard, « Anomalie » sans un mot ne se relit pas."""
        assert justification_manquante(statut, None)
        assert justification_manquante(statut, "   ")
        assert not justification_manquante(statut, "Batch resté sur la date de la veille.")

    @pytest.mark.parametrize("statut", [A_FAIRE, EN_COURS, COMPLETE])
    def test_le_cours_normal_des_choses_ne_se_justifie_pas(self, statut: str) -> None:
        assert not justification_manquante(statut, None)


class TestLaSoireeEstUneActiviteCommeLesAutres:
    """Le module doit être déclaré partout où le socle commun l'attend."""

    def test_le_module_est_enregistre(self) -> None:
        assert "eod" in MODULES
        assert PREFIXE_REFERENCE["eod"] == "EOD"
        assert CHEMIN_MODULE["eod"] == "/eod"

    def test_une_notification_mene_a_la_soiree_et_non_a_l_accueil(self) -> None:
        assert lien_activite("https://dsi360", "eod", "n1") == "https://dsi360/eod/n1"

    def test_le_cycle_part_de_la_preparation(self) -> None:
        assert etat_initial("eod") == "Préparé"

    def test_les_deux_facons_d_aboutir_sont_distinguees(self) -> None:
        """« Clôturé » dit que rien n'a dérapé ; « avec réserves » dit le contraire."""
        assert phase("eod", "Clôturé") == "termine"
        assert phase("eod", "Clôturé avec réserves") == "termine"
        assert ETATS["eod"]["Clôturé"].ton == "succes"
        assert ETATS["eod"]["Clôturé avec réserves"].ton == "attente"

    def test_une_soiree_close_ne_bouge_plus(self) -> None:
        assert est_etat_terminal("eod", "Clôturé")
        assert not est_etat_terminal("eod", "En cours")

    def test_une_soiree_annulee_ne_compte_dans_aucun_taux(self) -> None:
        """Maintenance, arrêt décidé : la nuit n'a pas eu lieu, elle n'est pas une nuit ratée."""
        assert phase("eod", "Annulé") == "abandonne"


def test_le_titre_se_lit_dans_une_liste_melee() -> None:
    """« Mes tickets » affiche des modules mêlés : le titre doit se suffire à lui-même."""
    assert titre_journee(datetime(2026, 9, 15).date()) == "EOD du 15/09/2026"

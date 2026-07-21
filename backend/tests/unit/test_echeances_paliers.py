"""Paliers de rappel : deux alertes avant l'échéance, une le jour même.

Le point délicat est le SLA : son délai va de 15 minutes à 5 jours, donc ses paliers se comptent
en part du temps consommé et non en jours. Les autres échéances sont des dates posées à l'avance,
sans durée de référence : seul le temps qu'il reste compte.
"""

from datetime import UTC, datetime, timedelta

import pytest

from dsi360.application.echeances import (
    FENETRE_RATTRAPAGE,
    PALIERS_JOURS,
    Echeance,
    paliers_dus,
    trop_ancien,
)


def _sla(cree: datetime, echeance: datetime) -> Echeance:
    return Echeance(
        nature="sla",
        cible_id="00000000-0000-0000-0000-000000000001",
        echeance=echeance,
        depart=cree,
        destinataire_id="u1",
        activite_id="a1",
        module="incident",
        reference="INC-2026-0001",
        objet="Panne",
    )


def _date(nature: str, echeance: datetime) -> Echeance:
    return Echeance(
        nature=nature,
        cible_id="00000000-0000-0000-0000-000000000002",
        echeance=echeance,
        depart=None,
        destinataire_id="u1",
        activite_id="a1",
        module="projet",
        reference="PRJ-2026-0001",
        objet="Migration",
    )


DEBUT = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)


class TestSla:
    """Un SLA de 4 h et un SLA de 5 j doivent tous deux prévenir en temps utile."""

    @pytest.mark.parametrize("heures", [0.25, 4, 24, 120])
    def test_les_trois_paliers_tombent_dans_le_delai(self, heures: float) -> None:
        fin = DEBUT + timedelta(hours=heures)
        e = _sla(DEBUT, fin)
        # À mi-parcours : un seul palier. Juste avant la fin : deux. À l'échéance : les trois.
        assert paliers_dus(e, DEBUT + timedelta(hours=heures * 0.5)) == ["avant_2"]
        assert paliers_dus(e, DEBUT + timedelta(hours=heures * 0.8)) == ["avant_2", "avant_1"]
        assert paliers_dus(e, fin) == ["avant_2", "avant_1", "jour_j"]

    def test_rien_au_tout_debut(self) -> None:
        e = _sla(DEBUT, DEBUT + timedelta(hours=4))
        assert paliers_dus(e, DEBUT) == []
        assert paliers_dus(e, DEBUT + timedelta(minutes=30)) == []

    def test_un_sla_court_previent_avant_de_depasser(self) -> None:
        """Le cas que l'ancien palier fixe (2 h avant) ne traitait pas : un SLA de 15 min."""
        fin = DEBUT + timedelta(minutes=15)
        e = _sla(DEBUT, fin)
        avant = paliers_dus(e, fin - timedelta(minutes=1))
        assert avant, "un SLA court doit alerter AVANT son dépassement"
        assert "jour_j" not in avant

    def test_un_delai_nul_ne_fait_pas_exploser_le_calcul(self) -> None:
        """Donnée limite : échéance égale à la création (import incohérent)."""
        e = _sla(DEBUT, DEBUT)
        assert paliers_dus(e, DEBUT) == ["avant_2", "avant_1", "jour_j"]


class TestEcheancesDatees:
    @pytest.mark.parametrize("nature", sorted(PALIERS_JOURS))
    def test_les_paliers_suivent_le_bareme_de_la_nature(self, nature: str) -> None:
        tot, moyen, _ = PALIERS_JOURS[nature]
        fin = datetime(2026, 8, 1, tzinfo=UTC)
        e = _date(nature, fin)

        assert paliers_dus(e, fin - timedelta(days=tot + 1)) == [], "trop tôt"
        assert paliers_dus(e, fin - timedelta(days=tot)) == ["avant_2"]
        assert paliers_dus(e, fin - timedelta(days=moyen)) == ["avant_2", "avant_1"]
        assert paliers_dus(e, fin) == ["avant_2", "avant_1", "jour_j"]

    def test_une_echeance_depassee_reste_au_dernier_palier(self) -> None:
        """Passé l'échéance, on ne réinvente pas un quatrième rappel."""
        fin = datetime(2026, 8, 1, tzinfo=UTC)
        e = _date("tache", fin)
        assert paliers_dus(e, fin + timedelta(days=30)) == ["avant_2", "avant_1", "jour_j"]

    def test_l_horizon_s_elargit_avec_l_objet(self) -> None:
        """Une tâche se rattrape en un jour, une fin de projet non : les barèmes le reflètent."""
        assert PALIERS_JOURS["tache"][0] < PALIERS_JOURS["jalon"][0]
        assert PALIERS_JOURS["jalon"][0] < PALIERS_JOURS["projet"][0]

    @pytest.mark.parametrize("nature", sorted(PALIERS_JOURS))
    def test_le_bareme_est_decroissant_et_finit_le_jour_j(self, nature: str) -> None:
        paliers = PALIERS_JOURS[nature]
        assert list(paliers) == sorted(paliers, reverse=True), "du plus tôt au plus tard"
        assert paliers[-1] == 0, "le dernier rappel tombe le jour de l'échéance"
        assert len(set(paliers)) == 3, "trois paliers distincts : deux avant, un le jour même"


class TestFenetreDeRattrapage:
    """Un rappel n'a de valeur que s'il est encore une nouvelle.

    Sans ce garde-fou, la première exécution après une mise en production enverrait un courriel
    pour chaque échéance déjà passée — des dizaines d'un coup, sur des retards connus de tous.
    """

    def test_un_palier_tout_juste_du_part_bien(self) -> None:
        fin = datetime(2026, 8, 1, tzinfo=UTC)
        e = _date("tache", fin)
        assert not trop_ancien(e, "jour_j", fin)
        assert not trop_ancien(e, "jour_j", fin + timedelta(days=1))

    def test_un_retard_ancien_ne_declenche_plus_de_courriel(self) -> None:
        fin = datetime(2026, 8, 1, tzinfo=UTC)
        e = _date("tache", fin)
        tardif = fin + FENETRE_RATTRAPAGE + timedelta(days=1)
        assert trop_ancien(e, "jour_j", tardif)
        # Le palier reste néanmoins consommé : il ne repartira pas non plus plus tard.
        assert paliers_dus(e, tardif) == ["avant_2", "avant_1", "jour_j"]

    def test_la_regle_vaut_aussi_pour_le_sla(self) -> None:
        fin = DEBUT + timedelta(hours=4)
        e = _sla(DEBUT, fin)
        assert not trop_ancien(e, "jour_j", fin + timedelta(hours=1))
        assert trop_ancien(e, "jour_j", fin + FENETRE_RATTRAPAGE + timedelta(hours=1))

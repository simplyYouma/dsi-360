"""Rappels d'échéance de bout en bout : les tâches sont enfin couvertes, et sans doublon.

Jusqu'ici une échéance de tâche ne déclenchait rien du tout, et le SLA n'alertait qu'une fois.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.echeances import _collecter, paliers_dus
from tests.integration.conftest import creer_activite, creer_utilisateur


async def _tache(session: AsyncSession, activite_id: str, assigne: str, echeance: date) -> str:
    ident = await session.scalar(
        text(
            "INSERT INTO core.tache (activite_id, titre, assigne_id, echeance) "
            "VALUES (cast(:a as uuid), 'Rédiger le plan', cast(:u as uuid), :e) "
            "RETURNING id::text"
        ),
        {"a": activite_id, "u": assigne, "e": echeance},
    )
    await session.commit()
    return str(ident)


async def test_une_echeance_de_tache_est_surveillee(session: AsyncSession) -> None:
    """Le manque le plus criant : aucune tâche n'était rappelée, quelle que soit son échéance."""
    agent = await creer_utilisateur(session, email="agent.ech@afgbank.ml")
    projet = await creer_activite(session, module="projet", reference="PRJ-ECH-1")
    await _tache(session, projet, agent, date(2026, 8, 1))

    echeances = await _collecter(session)
    taches = [e for e in echeances if e.nature == "tache" and e.reference == "PRJ-ECH-1"]

    assert len(taches) == 1, "la tâche doit être vue par le scanner"
    e = taches[0]
    assert e.destinataire_id == agent, "c'est l'assigné qu'on prévient"
    assert e.objet == "Rédiger le plan"

    # J-3, J-1, jour J — les trois paliers de la nature « tâche ».
    fin = datetime(2026, 8, 1, tzinfo=UTC)
    assert paliers_dus(e, fin - timedelta(days=5)) == []
    assert paliers_dus(e, fin - timedelta(days=3)) == ["avant_2"]
    assert paliers_dus(e, fin) == ["avant_2", "avant_1", "jour_j"]


async def test_une_tache_terminee_ne_rappelle_plus(session: AsyncSession) -> None:
    """Rappeler l'échéance d'une tâche faite serait du bruit pur."""
    agent = await creer_utilisateur(session, email="agent.ech2@afgbank.ml")
    projet = await creer_activite(session, module="projet", reference="PRJ-ECH-2")
    tache = await _tache(session, projet, agent, date(2026, 8, 1))
    await session.execute(
        text("UPDATE core.tache SET statut = 'Terminée' WHERE id = cast(:t as uuid)"),
        {"t": tache},
    )
    await session.commit()

    echeances = await _collecter(session)

    assert not [e for e in echeances if e.reference == "PRJ-ECH-2"]


async def test_une_tache_sans_assigne_ne_rappelle_personne(session: AsyncSession) -> None:
    """Sans destinataire, il n'y a personne à prévenir : on ne notifie pas dans le vide."""
    projet = await creer_activite(session, module="projet", reference="PRJ-ECH-3")
    await session.execute(
        text(
            "INSERT INTO core.tache (activite_id, titre, echeance) "
            "VALUES (cast(:a as uuid), 'Orpheline', cast('2026-08-01' as date))"
        ),
        {"a": projet},
    )
    await session.commit()

    echeances = await _collecter(session)

    assert not [e for e in echeances if e.reference == "PRJ-ECH-3"]


async def test_un_palier_ne_part_qu_une_fois(session: AsyncSession) -> None:
    """La table de rappels garantit l'unicité ; l'ancien index n'autorisait qu'UNE alerte SLA."""
    marquer = text(
        "INSERT INTO core.rappel_echeance (cible_type, cible_id, echeance, palier) "
        "VALUES ('tache', cast(:c as uuid), :e, :p) ON CONFLICT DO NOTHING RETURNING palier"
    )
    cible = await creer_activite(session, module="projet", reference="PRJ-ECH-4")
    quand = datetime(2026, 8, 1, tzinfo=UTC)

    premier = await session.scalar(marquer, {"c": cible, "e": quand, "p": "avant_2"})
    second = await session.scalar(marquer, {"c": cible, "e": quand, "p": "avant_2"})
    # Un autre palier de la même échéance reste possible : ce sont bien trois alertes distinctes.
    autre = await session.scalar(marquer, {"c": cible, "e": quand, "p": "avant_1"})
    # Échéance repoussée : les rappels repartent sur la nouvelle date.
    repoussee = await session.scalar(
        marquer, {"c": cible, "e": quand + timedelta(days=7), "p": "avant_2"}
    )
    await session.commit()

    assert premier == "avant_2"
    assert second is None, "le même palier ne repart pas"
    assert autre == "avant_1"
    assert repoussee == "avant_2", "une nouvelle échéance porte ses propres rappels"

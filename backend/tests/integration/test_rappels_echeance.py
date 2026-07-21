"""Rappels d'échéance de bout en bout : les tâches sont enfin couvertes, et sans doublon.

Jusqu'ici une échéance de tâche ne déclenchait rien du tout, et le SLA n'alertait qu'une fois.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.echeances import _collecter, paliers_dus
from tests.integration.conftest import creer_activite, creer_utilisateur, designer


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


async def test_le_responsable_du_dossier_est_prevenu_lui_aussi(session: AsyncSession) -> None:
    """Le chef de projet répond du planning : il suit les échéances de tâches, comme le porteur."""
    chef = await creer_utilisateur(session, email="chef.ech@afgbank.ml")
    agent = await creer_utilisateur(session, email="porteur.ech@afgbank.ml")
    projet = await creer_activite(
        session, module="projet", reference="PRJ-ECH-CHEF", responsable_id=chef
    )
    await _tache(session, projet, agent, date(2026, 8, 1))

    echeances = await _collecter(session)
    destinataires = {
        e.destinataire_id
        for e in echeances
        if e.reference == "PRJ-ECH-CHEF" and e.nature == "tache"
    }

    assert destinataires == {chef, agent}, "le porteur ET le responsable du dossier"


async def test_un_changement_previent_aussi_son_gestionnaire(session: AsyncSession) -> None:
    """Même règle hors projet : le gestionnaire du changement suit les échéances de ses tâches."""
    gestionnaire = await creer_utilisateur(session, email="gest.ech@afgbank.ml")
    agent = await creer_utilisateur(session, email="porteur.chg@afgbank.ml")
    chg = await creer_activite(
        session, module="changement", reference="CHG-ECH-1", responsable_id=gestionnaire
    )
    await _tache(session, chg, agent, date(2026, 8, 1))

    echeances = await _collecter(session)
    destinataires = {
        e.destinataire_id
        for e in echeances
        if e.reference == "CHG-ECH-1" and e.nature == "tache"
    }

    assert destinataires == {gestionnaire, agent}


async def test_le_porteur_qui_est_aussi_responsable_n_est_prevenu_qu_une_fois(
    session: AsyncSession,
) -> None:
    """Un chef de projet qui porte sa propre tâche ne doit pas recevoir deux fois le même rappel."""
    chef = await creer_utilisateur(session, email="chef.solo@afgbank.ml")
    projet = await creer_activite(
        session, module="projet", reference="PRJ-ECH-SOLO", responsable_id=chef
    )
    await _tache(session, projet, chef, date(2026, 8, 1))

    echeances = [
        e
        for e in await _collecter(session)
        if e.reference == "PRJ-ECH-SOLO" and e.nature == "tache"
    ]

    assert len(echeances) == 1, "une seule ligne quand les deux rôles sont la même personne"


async def test_le_contributeur_est_prevenu_lui_aussi(session: AsyncSession) -> None:
    """Un renfort travaille sur le dossier : il doit voir venir l'échéance comme les autres."""
    chef = await creer_utilisateur(session, email="chef.contrib@afgbank.ml")
    porteur = await creer_utilisateur(session, email="porteur.contrib@afgbank.ml")
    renfort = await creer_utilisateur(session, email="renfort.contrib@afgbank.ml")
    projet = await creer_activite(
        session, module="projet", reference="PRJ-CONTRIB", responsable_id=chef
    )
    await designer(session, activite_id=projet, utilisateur_id=renfort, role="CONTRIBUTEUR")
    await _tache(session, projet, porteur, date(2026, 8, 1))
    await session.commit()

    echeances = await _collecter(session)
    destinataires = {
        e.destinataire_id
        for e in echeances
        if e.reference == "PRJ-CONTRIB" and e.nature == "tache"
    }

    assert destinataires == {chef, porteur, renfort}


async def test_le_contributeur_suit_aussi_les_echeances_du_dossier(
    session: AsyncSession,
) -> None:
    """Pas seulement les tâches : le SLA du dossier le concerne autant que son gestionnaire."""
    gestionnaire = await creer_utilisateur(session, email="gest.sla@afgbank.ml")
    renfort = await creer_utilisateur(session, email="renfort.sla@afgbank.ml")
    inc = await creer_activite(
        session, module="incident", reference="INC-CONTRIB", responsable_id=gestionnaire
    )
    await designer(session, activite_id=inc, utilisateur_id=renfort, role="CONTRIBUTEUR")
    await session.commit()

    echeances = await _collecter(session)
    destinataires = {
        e.destinataire_id for e in echeances if e.reference == "INC-CONTRIB" and e.nature == "sla"
    }

    assert destinataires == {gestionnaire, renfort}


async def test_un_valideur_ne_recoit_pas_les_rappels(session: AsyncSession) -> None:
    """Le valideur décide, il ne porte pas le planning : le prévenir serait du bruit."""
    gestionnaire = await creer_utilisateur(session, email="gest.val@afgbank.ml")
    valideur = await creer_utilisateur(session, email="valideur.ech@afgbank.ml")
    inc = await creer_activite(
        session, module="incident", reference="INC-VALIDEUR", responsable_id=gestionnaire
    )
    await designer(session, activite_id=inc, utilisateur_id=valideur, role="VALIDEUR")
    await session.commit()

    echeances = await _collecter(session)
    destinataires = {e.destinataire_id for e in echeances if e.reference == "INC-VALIDEUR"}

    assert destinataires == {gestionnaire}


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
        "INSERT INTO core.rappel_echeance "
        "(cible_type, cible_id, destinataire_id, echeance, palier) "
        "VALUES ('tache', cast(:c as uuid), cast(:d as uuid), :e, :p) "
        "ON CONFLICT DO NOTHING RETURNING palier"
    )
    cible = await creer_activite(session, module="projet", reference="PRJ-ECH-4")
    agent = await creer_utilisateur(session, email="agent.uniq@afgbank.ml")
    autre_agent = await creer_utilisateur(session, email="chef.uniq@afgbank.ml")
    quand = datetime(2026, 8, 1, tzinfo=UTC)
    base = {"c": cible, "d": agent, "e": quand}

    premier = await session.scalar(marquer, {**base, "p": "avant_2"})
    second = await session.scalar(marquer, {**base, "p": "avant_2"})
    # Un autre palier de la même échéance reste possible : ce sont bien trois alertes distinctes.
    autre = await session.scalar(marquer, {**base, "p": "avant_1"})
    # Le second destinataire (chef de projet) reçoit le sien : le palier n'est pas « consommé »
    # pour tout le monde par le premier envoi.
    voisin = await session.scalar(marquer, {**base, "d": autre_agent, "p": "avant_2"})
    # Échéance repoussée : les rappels repartent sur la nouvelle date.
    repoussee = await session.scalar(
        marquer, {**base, "e": quand + timedelta(days=7), "p": "avant_2"}
    )
    await session.commit()

    assert premier == "avant_2"
    assert second is None, "le même palier ne repart pas pour la même personne"
    assert autre == "avant_1"
    assert voisin == "avant_2", "chaque destinataire a son propre rappel"
    assert repoussee == "avant_2", "une nouvelle échéance porte ses propres rappels"


async def test_reassigner_une_tache_previent_les_deux_agents(session: AsyncSession) -> None:
    """L'ancien porteur doit l'apprendre : sinon il croit encore la tâche sienne, ou l'abandonne.

    L'assignation d'activité prévenait déjà les deux ; celle des tâches oubliait l'ancien.
    """
    from dsi360.application.taches import maj_tache
    from dsi360.infrastructure.repositories import tache as repo_tache

    admin = await creer_utilisateur(session, email="admin.rea@afgbank.ml", profil="ADMIN")
    ancien = await creer_utilisateur(session, email="ancien.rea@afgbank.ml")
    nouveau = await creer_utilisateur(session, email="nouveau.rea@afgbank.ml")
    projet = await creer_activite(session, module="projet", reference="PRJ-REA-1")
    tache_id = await _tache(session, projet, ancien, date(2026, 8, 1))

    tache = await repo_tache.par_id(session, tache_id)
    assert tache is not None
    await maj_tache(
        session,
        dict(tache),
        "projet",
        {"assigne_id": nouveau},
        {"id": admin, "email": "admin.rea@afgbank.ml"},
    )
    await session.commit()

    recus = (
        await session.execute(
            text(
                "SELECT destinataire_id::text AS d, titre FROM core.notification "
                "WHERE type = 'TACHE' AND activite_id = cast(:a as uuid)"
            ),
            {"a": projet},
        )
    ).mappings().all()
    par_agent = {r["d"]: r["titre"] for r in recus}

    assert "réattribuée" in par_agent[ancien].lower(), "l'ancien apprend qu'on la lui retire"
    assert "assignée" in par_agent[nouveau].lower(), "le nouveau apprend qu'il la reçoit"

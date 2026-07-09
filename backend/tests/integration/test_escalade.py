"""Escalade de support : N1 → N2 à la DSI, puis N3 = transfert à DBS (ADR-0003 §3).

DBS n'a aucun compte dans le système. Escalader un ticket déjà en N2 ne le réaffecte donc à
personne : il est marqué « transféré à DBS » et **garde son gestionnaire DSI**, qui n'en assure
plus le traitement mais le suivi et la relance. Le SLA continue de courir : c'est l'engagement pris
envers le demandeur, qui ignore quelle équipe traite.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _creer_incident(
    session: AsyncSession,
    *,
    reference: str,
    responsable_id: str | None = None,
    niveau: int | None = None,
) -> str:
    donnees: dict[str, Any] = {} if niveau is None else {"niveau_support": niveau}
    import json

    ident = await session.scalar(
        text(
            "INSERT INTO core.activite "
            "(reference, module, titre, statut, priorite, impact, urgence, direction_id, "
            " responsable_id, sla_resolution_le, donnees) "
            "VALUES (:reference, 'incident', 'Incident de test', 'Nouveau', 3, 3, 3, "
            "        (SELECT id FROM core.direction WHERE code = 'DSI'), "
            "        cast(:resp as uuid), now() + interval '2 days', cast(:donnees as jsonb)) "
            "RETURNING id::text"
        ),
        {"reference": reference, "resp": responsable_id, "donnees": json.dumps(donnees)},
    )
    await session.commit()
    return str(ident)


async def _echeance(session: AsyncSession, ident: str) -> Any:
    return await session.scalar(
        text("SELECT sla_resolution_le FROM core.activite WHERE id = cast(:id as uuid)"),
        {"id": ident},
    )


async def test_escalade_n1_vers_n2_reaffecte_a_un_agent_n2(
    client: AsyncClient, session: AsyncSession
) -> None:
    n1 = await creer_utilisateur(session, email="n1.esc@afgbank.ml")
    n2 = await creer_utilisateur(session, email="n2.esc@afgbank.ml")
    await session.execute(
        text("UPDATE core.utilisateur SET niveau_support = 1 WHERE id = cast(:i as uuid)"),
        {"i": n1},
    )
    await session.execute(
        text("UPDATE core.utilisateur SET niveau_support = 2 WHERE id = cast(:i as uuid)"),
        {"i": n2},
    )
    await session.commit()
    incident = await _creer_incident(
        session, reference="INC-ESC-0001", responsable_id=n1, niveau=1
    )

    r = await client.post(f"/incidents/{incident}/escalader", headers=entetes(n1))

    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["niveau_support"] == 2
    assert corps["transfere_dbs"] is False
    assert corps["responsable_id"] == n2, "le ticket passe à l'agent N2 le moins chargé"


async def test_escalade_n2_transfere_a_dbs_et_garde_le_gestionnaire(
    client: AsyncClient, session: AsyncSession
) -> None:
    n2 = await creer_utilisateur(session, email="n2.dbs@afgbank.ml")
    await session.execute(
        text("UPDATE core.utilisateur SET niveau_support = 2 WHERE id = cast(:i as uuid)"),
        {"i": n2},
    )
    await session.commit()
    incident = await _creer_incident(
        session, reference="INC-ESC-0002", responsable_id=n2, niveau=2
    )

    r = await client.post(f"/incidents/{incident}/escalader", headers=entetes(n2))

    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["niveau_support"] == 3
    assert corps["transfere_dbs"] is True
    assert corps["responsable_id"] == n2, "l'agent reste référent du suivi (ADR-0003 §3)"


async def test_le_transfert_a_dbs_ne_touche_pas_l_echeance_sla(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le SLA court toujours : le demandeur ignore quelle équipe traite son ticket."""
    n2 = await creer_utilisateur(session, email="n2.sla@afgbank.ml")
    await session.execute(
        text("UPDATE core.utilisateur SET niveau_support = 2 WHERE id = cast(:i as uuid)"),
        {"i": n2},
    )
    await session.commit()
    incident = await _creer_incident(
        session, reference="INC-ESC-0003", responsable_id=n2, niveau=2
    )
    avant = await _echeance(session, incident)

    await client.post(f"/incidents/{incident}/escalader", headers=entetes(n2))

    assert await _echeance(session, incident) == avant


async def test_escalader_un_ticket_deja_chez_dbs_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    n2 = await creer_utilisateur(session, email="n2.deja@afgbank.ml")
    await session.execute(
        text("UPDATE core.utilisateur SET niveau_support = 2 WHERE id = cast(:i as uuid)"),
        {"i": n2},
    )
    await session.commit()
    incident = await _creer_incident(
        session, reference="INC-ESC-0004", responsable_id=n2, niveau=3
    )

    r = await client.post(f"/incidents/{incident}/escalader", headers=entetes(n2))

    assert r.status_code == 409, r.text
    assert "DBS" in r.json()["detail"]


async def test_escalade_sans_agent_n2_disponible_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Refus explicite plutôt que transfert silencieux à DBS : le N2 n'a pas été tenté."""
    n1 = await creer_utilisateur(session, email="n1.seul@afgbank.ml")
    await session.execute(
        text("UPDATE core.utilisateur SET niveau_support = 1 WHERE id = cast(:i as uuid)"),
        {"i": n1},
    )
    # Aucun agent N2 : on neutralise ceux du jeu de données.
    await session.execute(
        text("UPDATE core.utilisateur SET niveau_support = NULL WHERE niveau_support = 2")
    )
    await session.commit()
    incident = await _creer_incident(
        session, reference="INC-ESC-0005", responsable_id=n1, niveau=1
    )

    r = await client.post(f"/incidents/{incident}/escalader", headers=entetes(n1))

    assert r.status_code == 409, r.text
    assert "N2" in r.json()["detail"]


async def test_escalader_un_ticket_sans_gestionnaire_le_transfere_a_dbs(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Personne ne l'a pris à la DSI : l'escalader, c'est le passer à DBS. Sans gestionnaire."""
    agent = await creer_utilisateur(session, email="agent.orphelin@afgbank.ml")
    incident = await _creer_incident(session, reference="INC-ESC-0006", responsable_id=None)

    r = await client.post(f"/incidents/{incident}/escalader", headers=entetes(agent))

    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["niveau_support"] == 3
    assert corps["transfere_dbs"] is True
    assert corps["responsable_id"] is None


async def test_le_transfert_est_journalise(client: AsyncClient, session: AsyncSession) -> None:
    n2 = await creer_utilisateur(session, email="n2.audit@afgbank.ml")
    admin = await creer_utilisateur(session, email="admin.esc@afgbank.ml", profil="ADMIN")
    await session.execute(
        text("UPDATE core.utilisateur SET niveau_support = 2 WHERE id = cast(:i as uuid)"),
        {"i": n2},
    )
    await session.commit()
    incident = await _creer_incident(
        session, reference="INC-ESC-0007", responsable_id=n2, niveau=2
    )

    await client.post(f"/incidents/{incident}/escalader", headers=entetes(n2))

    journal = (await client.get("/admin/journal?page=1", headers=entetes(admin))).json()
    escalades = [e for e in journal["elements"] if e["cible"] == "INC-ESC-0007"]
    assert escalades, "le transfert vers DBS doit laisser une trace"
    assert escalades[0]["action"] == "ESCALADE"

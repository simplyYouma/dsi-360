"""Export de la discussion interne d'une activité (CSV / Excel)."""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def test_exporter_la_discussion(client: AsyncClient, session: AsyncSession) -> None:
    agent = await creer_utilisateur(session, email="disc.export@afgbank.ml")
    activite = await creer_activite(session, module="changement", reference="CHG-DISC-1")
    await session.execute(
        text(
            "INSERT INTO core.commentaire (activite_id, texte, auteur_id, auteur_email) "
            "VALUES (cast(:a as uuid), 'Premier message', cast(:u as uuid), :e)"
        ),
        {"a": activite, "u": agent, "e": "disc.export@afgbank.ml"},
    )
    await session.commit()

    r = await client.get(f"/commentaires/{activite}/export?format=csv", headers=entetes(agent))
    assert r.status_code == 200, r.text
    corps = r.content.decode("utf-8-sig")
    assert "Message" in corps and "Premier message" in corps

    r = await client.get(f"/commentaires/{activite}/export?format=xlsx", headers=entetes(agent))
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]

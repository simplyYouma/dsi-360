"""« Mes tickets » vu par un administrateur : consulter la file d'un gestionnaire.

Un admin n'a presque jamais de tickets ; il doit pouvoir regarder la file d'un agent — ses
tickets, tâches et analyses — comme si c'était lui, en lecture. Réservé à l'administrateur.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def test_admin_consulte_la_file_d_un_agent(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.vue@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.vue@afgbank.ml")
    await creer_activite(
        session, module="changement", reference="CHG-VUE-1", responsable_id=agent
    )

    # Sa propre file : l'admin n'a rien.
    r = await client.get("/mes-tickets", headers=entetes(admin))
    assert r.status_code == 200
    assert all(e["reference"] != "CHG-VUE-1" for e in r.json()["elements"])

    # La file de l'agent : le ticket y est.
    r = await client.get(f"/mes-tickets?agent={agent}", headers=entetes(admin))
    assert r.status_code == 200, r.text
    assert any(e["reference"] == "CHG-VUE-1" for e in r.json()["elements"])

    # Les analyses portent bien le nom de l'agent consulté, pas celui de l'admin.
    r = await client.get(f"/mes-tickets/stats?agent={agent}", headers=entetes(admin))
    assert r.status_code == 200, r.text
    assert "agent.vue" not in r.json()["agent"]["nom"].lower()  # nom, pas e-mail
    assert r.json()["ouverts"] >= 1


async def test_un_non_admin_ne_voit_pas_la_file_d_autrui(
    client: AsyncClient, session: AsyncSession
) -> None:
    agent = await creer_utilisateur(session, email="agent1.vue@afgbank.ml")
    autre = await creer_utilisateur(session, email="agent2.vue@afgbank.ml")

    r = await client.get(f"/mes-tickets?agent={autre}", headers=entetes(agent))
    assert r.status_code == 403, r.text

    # Viser sa propre file via ?agent reste permis (c'est soi-même).
    r = await client.get(f"/mes-tickets?agent={agent}", headers=entetes(agent))
    assert r.status_code == 200, r.text


async def test_admin_agent_inconnu(client: AsyncClient, session: AsyncSession) -> None:
    admin = await creer_utilisateur(session, email="admin.inconnu@afgbank.ml", profil="ADMIN")
    r = await client.get(
        "/mes-tickets?agent=00000000-0000-0000-0000-000000000000", headers=entetes(admin)
    )
    assert r.status_code == 404, r.text

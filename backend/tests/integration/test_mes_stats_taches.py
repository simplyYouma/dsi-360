"""« Mes tickets » compte aussi les projets et les tâches — pas seulement les tickets.

Les projets entrent dans la file de l'agent au même titre que les changements, et les tâches
qui lui sont assignées (projets, changements) comptent comme du travail dans ses analyses.
"""

from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def test_un_projet_entre_dans_la_file_et_les_stats(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le projet dont l'agent est chef apparaît dans « Mes tickets » comme les autres modules."""
    agent = await creer_utilisateur(session, email="agent.projfile@afgbank.ml")
    await creer_activite(
        session, module="projet", reference="PRJ-FILE-1", responsable_id=agent
    )

    file = await client.get("/mes-tickets", headers=entetes(agent))
    assert any(e["reference"] == "PRJ-FILE-1" for e in file.json()["elements"])

    stats = await client.get("/mes-tickets/stats", headers=entetes(agent))
    modules = {c["libelle"] for c in stats.json()["par_module"]}
    assert "projet" in modules, "le projet compte dans la répartition par module"


async def test_les_taches_en_retard_comptent_dans_les_stats(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Une tâche assignée à l'agent, échéance dépassée, remonte dans stats.taches.en_retard."""
    admin = await creer_utilisateur(session, email="admin.tstat@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.tstat@afgbank.ml")
    projet = await creer_activite(
        session, module="projet", reference="PRJ-TST-1", responsable_id=agent
    )
    hier = (date.today() - timedelta(days=3)).isoformat()

    # L'admin distribue une tâche à l'agent, déjà en retard.
    r = await client.post(
        f"/projets/{projet}/taches",
        headers=entetes(admin),
        json={"titre": "Cadrer le besoin", "assigne_id": agent, "echeance": hier},
    )
    assert r.status_code in (200, 201), r.text

    stats = (await client.get("/mes-tickets/stats", headers=entetes(agent))).json()
    assert stats["taches"]["en_retard"] >= 1, "la tâche en retard doit compter dans les analyses"
    assert stats["taches"]["a_faire"] + stats["taches"]["en_cours"] >= 1

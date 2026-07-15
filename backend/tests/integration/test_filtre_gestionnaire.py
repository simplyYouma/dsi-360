"""Filtrer une liste par personne : gestionnaire ET contributeur.

Filtrer sur quelqu'un, c'est vouloir tout ce dont il s'occupe — ce qu'il gère, mais aussi ce à
quoi il contribue. Une activité confiée en renfort ne doit pas disparaître de son filtre.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, designer, entetes


async def test_le_filtre_gestionnaire_inclut_les_contributions(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.filtre@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.filtre@afgbank.ml")
    autre = await creer_utilisateur(session, email="autre.filtre@afgbank.ml")

    # A : l'agent en est le gestionnaire. B : quelqu'un d'autre gère, l'agent contribue.
    await creer_activite(
        session, module="changement", reference="CHG-FILT-A", responsable_id=agent
    )
    contribue = await creer_activite(
        session, module="changement", reference="CHG-FILT-B", responsable_id=autre
    )
    await designer(session, activite_id=contribue, utilisateur_id=agent, role="CONTRIBUTEUR")
    # C : ni géré ni contribué par l'agent — ne doit pas apparaître.
    await creer_activite(
        session, module="changement", reference="CHG-FILT-C", responsable_id=autre
    )

    r = await client.get(f"/changements?responsable_id={agent}", headers=entetes(admin))
    assert r.status_code == 200, r.text
    refs = {e["reference"] for e in r.json()["elements"]}
    assert "CHG-FILT-A" in refs, "l'activité gérée"
    assert "CHG-FILT-B" in refs, "l'activité où l'agent est contributeur"
    assert "CHG-FILT-C" not in refs, "aucune raison d'y figurer"

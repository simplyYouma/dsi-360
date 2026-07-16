"""Filtrer une liste par personne : gestionnaire ET contributeur.

Filtrer sur quelqu'un, c'est vouloir tout ce dont il s'occupe — ce qu'il gère, mais aussi ce à
quoi il contribue. Une activité confiée en renfort ne doit pas disparaître de son filtre.
"""

from httpx import AsyncClient
from sqlalchemy import text
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


async def test_non_assigne_ne_ramene_ni_dbs_ni_les_tickets_avec_renfort(
    client: AsyncClient, session: AsyncSession
) -> None:
    """« Non assigné » = personne, vraiment.

    Un ticket confié à DBS n'a pas de compte chez nous, mais il est assigné — à eux. Un ticket où
    l'un des nôtres contribue n'est pas orphelin non plus. Ni l'un ni l'autre n'est « non assigné ».
    """
    admin = await creer_utilisateur(session, email="admin.na@afgbank.ml", profil="ADMIN")
    renfort = await creer_utilisateur(session, email="renfort.na@afgbank.ml")

    await creer_activite(session, module="incident", reference="INC-NA-ORPHELIN")
    chez_dbs = await creer_activite(session, module="incident", reference="INC-NA-DBS")
    await session.execute(
        text(
            "UPDATE core.activite SET donnees = donnees || "
            "jsonb_build_object('gestionnaire', cast(:n as text)) WHERE id = cast(:i as uuid)"
        ),
        {"n": "Agent DBS", "i": chez_dbs},
    )
    avec_renfort = await creer_activite(session, module="incident", reference="INC-NA-RENFORT")
    await designer(session, activite_id=avec_renfort, utilisateur_id=renfort, role="CONTRIBUTEUR")
    await session.commit()

    r = await client.get("/incidents?non_assigne=true&etat=tous", headers=entetes(admin))

    assert r.status_code == 200, r.text
    refs = {e["reference"] for e in r.json()["elements"]}
    assert "INC-NA-ORPHELIN" in refs, "personne ne l'a pris : c'est bien un non assigné"
    assert "INC-NA-DBS" not in refs, "assigné à DBS, donc assigné"
    assert "INC-NA-RENFORT" not in refs, "un contributeur de chez nous s'en occupe"


async def test_le_filtre_dbs_ne_ramene_que_les_tickets_confies_a_dbs(
    client: AsyncClient, session: AsyncSession
) -> None:
    """La vue DBS : un gestionnaire nommé au fichier, aucun compte chez nous (ADR-0005)."""
    admin = await creer_utilisateur(session, email="admin.dbs@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.dbs@afgbank.ml")

    chez_dbs = await creer_activite(session, module="incident", reference="INC-DBS-OUI")
    await session.execute(
        text(
            "UPDATE core.activite SET donnees = donnees || "
            "jsonb_build_object('gestionnaire', cast(:n as text)) WHERE id = cast(:i as uuid)"
        ),
        {"n": "Agent DBS", "i": chez_dbs},
    )
    await creer_activite(session, module="incident", reference="INC-DBS-NOUS", responsable_id=agent)
    await creer_activite(session, module="incident", reference="INC-DBS-ORPHELIN")
    await session.commit()

    r = await client.get("/incidents?dbs=true&etat=tous", headers=entetes(admin))

    assert r.status_code == 200, r.text
    refs = {e["reference"] for e in r.json()["elements"]}
    assert "INC-DBS-OUI" in refs
    assert "INC-DBS-NOUS" not in refs, "géré par un compte DSI"
    assert "INC-DBS-ORPHELIN" not in refs, "personne ne s'en occupe, pas même DBS"

"""Description d'un incident/demande importé : saisissable par le module, jamais par l'import.

Le rapport quotidien n'a pas de colonne description : l'upsert ne la touche donc jamais, et une
saisie manuelle survit aux ré-imports. C'est une annotation interne, ouverte à tout agent du
module — comme la discussion et la désignation d'un contributeur.
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def test_le_gestionnaire_saisit_la_description(
    client: AsyncClient, session: AsyncSession
) -> None:
    gestionnaire = await creer_utilisateur(session, email="gest.desc@afgbank.ml")
    incident = await creer_activite(
        session, module="incident", reference="INC-DESC-1", responsable_id=gestionnaire
    )

    # Le droit est exposé, et la saisie passe.
    r = await client.get(f"/incidents/{incident}", headers=entetes(gestionnaire))
    assert r.json()["permissions"]["peut_editer_description"] is True

    r = await client.patch(
        f"/incidents/{incident}/description",
        headers=entetes(gestionnaire),
        json={"description": "Poste bloqué au démarrage, écran bleu."},
    )
    assert r.status_code == 200, r.text
    assert r.json()["description"] == "Poste bloqué au démarrage, écran bleu."


async def test_tout_agent_du_module_saisit_la_description(
    client: AsyncClient, session: AsyncSession
) -> None:
    """L'annotation n'est plus réservée aux acteurs : un simple agent du module la renseigne —
    comme la discussion. L'accès au module suffit ; le geste ne touche pas l'état du ticket."""
    gestionnaire = await creer_utilisateur(session, email="g2.desc@afgbank.ml")
    tiers = await creer_utilisateur(session, email="tiers.desc@afgbank.ml")
    incident = await creer_activite(
        session, module="incident", reference="INC-DESC-2", responsable_id=gestionnaire
    )

    r = await client.get(f"/incidents/{incident}", headers=entetes(tiers))
    assert r.json()["permissions"]["peut_editer_description"] is True

    r = await client.patch(
        f"/incidents/{incident}/description",
        headers=entetes(tiers),
        json={"description": "vu avec l'utilisateur"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["description"] == "vu avec l'utilisateur"


async def test_la_description_survit_a_un_reimport(
    client: AsyncClient, session: AsyncSession
) -> None:
    gestionnaire = await creer_utilisateur(session, email="g3.desc@afgbank.ml")
    incident = await creer_activite(
        session, module="incident", reference="INC-DESC-3", responsable_id=gestionnaire
    )
    await client.patch(
        f"/incidents/{incident}/description",
        headers=entetes(gestionnaire),
        json={"description": "Diagnostic en cours."},
    )
    # L'upsert d'import ne référence pas `description` : on simule sa mise à jour des autres champs.
    await session.execute(
        text("UPDATE core.activite SET titre = 'Titre rafraîchi par import' "
             "WHERE id = cast(:id as uuid)"),
        {"id": incident},
    )
    await session.commit()
    r = await client.get(f"/incidents/{incident}", headers=entetes(gestionnaire))
    assert r.json()["description"] == "Diagnostic en cours."

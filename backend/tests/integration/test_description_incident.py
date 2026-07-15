"""Description d'un incident/demande importé : saisissable par les acteurs, jamais par l'import.

Le rapport quotidien n'a pas de colonne description : l'upsert ne la touche donc jamais, et une
saisie manuelle survit aux ré-imports. Côté droits, seuls les acteurs de travail (gestionnaire,
contributeurs, administrateur) peuvent la renseigner.
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, designer, entetes


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


async def test_un_non_acteur_ne_saisit_pas(client: AsyncClient, session: AsyncSession) -> None:
    gestionnaire = await creer_utilisateur(session, email="g2.desc@afgbank.ml")
    tiers = await creer_utilisateur(session, email="tiers.desc@afgbank.ml")
    incident = await creer_activite(
        session, module="incident", reference="INC-DESC-2", responsable_id=gestionnaire
    )
    r = await client.patch(
        f"/incidents/{incident}/description",
        headers=entetes(tiers),
        json={"description": "tentative"},
    )
    assert r.status_code == 403, r.text

    # Un contributeur désigné, en revanche, peut saisir.
    await designer(session, activite_id=incident, utilisateur_id=tiers, role="CONTRIBUTEUR")
    r = await client.patch(
        f"/incidents/{incident}/description",
        headers=entetes(tiers),
        json={"description": "vu avec l'utilisateur"},
    )
    assert r.status_code == 200, r.text


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

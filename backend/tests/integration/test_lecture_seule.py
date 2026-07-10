"""Incidents et demandes : on observe, on n'agit pas.

Ces tickets sont traités dans un autre système. DSI 360 en suit l'évolution pour en tirer des
statistiques. Toute action qui prétendrait modifier l'état du ticket serait un mensonge : l'import
du lendemain l'effacerait.

Ce qui reste : lire, et la discussion interne à la DSI — nos échanges nous appartiennent, ils ne
viennent pas du fichier.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes

MODULES = ["incidents", "demandes"]


async def _ticket(session: AsyncSession, module: str, suffixe: str) -> tuple[str, str, str]:
    """Un ticket importé, un admin, un agent."""
    admin = await creer_utilisateur(session, email=f"admin.{suffixe}@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email=f"agent.{suffixe}@afgbank.ml")
    ident = await creer_activite(
        session,
        module="incident" if module == "incidents" else "demande",
        reference=f"{'INC' if module == 'incidents' else 'DEM'}-RO-{suffixe}",
        responsable_id=agent,
    )
    return ident, admin, agent


# --- L'état du ticket ne se modifie pas ici ------------------------------------------------------


@pytest.mark.parametrize("module", MODULES)
async def test_le_statut_ne_se_change_pas_a_la_main(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    ident, admin, _ = await _ticket(session, module, f"trans-{module}")
    vers = "Ouvert" if module == "incidents" else "Qualifiée"

    r = await client.post(
        f"/{module}/{ident}/transition", headers=entetes(admin), json={"vers": vers}
    )

    assert r.status_code == 404, r.text


@pytest.mark.parametrize("module", MODULES)
async def test_le_gestionnaire_ne_s_assigne_pas_a_la_main(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    """Le fichier décide du gestionnaire. Une assignation ici serait effacée demain."""
    ident, admin, agent = await _ticket(session, module, f"assign-{module}")

    r = await client.post(
        f"/{module}/{ident}/assignation", headers=entetes(admin), json={"responsable_id": agent}
    )

    assert r.status_code == 404, r.text


@pytest.mark.parametrize("module", MODULES)
async def test_l_assignation_en_lot_n_existe_plus(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    """405 : la route retirée, « assignation-lot » n'est plus qu'un identifiant, lisible en GET."""
    ident, admin, agent = await _ticket(session, module, f"lot-{module}")

    r = await client.post(
        f"/{module}/assignation-lot",
        headers=entetes(admin),
        json={"ids": [ident], "responsable_id": agent},
    )

    assert r.status_code == 405, r.text


@pytest.mark.parametrize("module", MODULES)
async def test_l_impact_et_l_urgence_ne_se_reevaluent_pas(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    """La priorité vient du fichier."""
    ident, admin, _ = await _ticket(session, module, f"eval-{module}")

    r = await client.post(
        f"/{module}/{ident}/evaluation", headers=entetes(admin), json={"impact": 5, "urgence": 5}
    )

    assert r.status_code == 404, r.text


@pytest.mark.parametrize("module", MODULES)
async def test_la_categorie_ne_se_change_pas(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    ident, admin, _ = await _ticket(session, module, f"cat-{module}")

    r = await client.post(
        f"/{module}/{ident}/categorie", headers=entetes(admin), json={"categorie_id": None}
    )

    assert r.status_code == 404, r.text


@pytest.mark.parametrize("module", MODULES)
async def test_on_ne_designe_ni_valideur_ni_decision(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    """Il n'y a rien à valider : le ticket est décidé dans l'autre système."""
    ident, admin, agent = await _ticket(session, module, f"acteurs-{module}")
    corps = {"utilisateur_id": agent}

    assert (
        await client.post(f"/{module}/{ident}/valideurs", headers=entetes(admin), json=corps)
    ).status_code == 404
    assert (
        await client.post(
            f"/{module}/{ident}/decision", headers=entetes(admin), json={"decision": "APPROUVE"}
        )
    ).status_code == 404


@pytest.mark.parametrize("module", MODULES)
async def test_l_admin_designe_un_contributeur_sur_un_ticket_importe(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    """La DSI suit un ticket qu'elle ne traite pas : le contributeur l'a dans sa file."""
    ident, admin, agent = await _ticket(session, module, f"contrib-{module}")

    r = await client.post(
        f"/{module}/{ident}/contributeurs", headers=entetes(admin), json={"utilisateur_id": agent}
    )

    assert r.status_code == 200, r.text
    assert not r.json()["permissions"]["peut_travailler"], "suivre n'est pas agir"

    files = await client.get("/mes-tickets", headers=entetes(agent))
    assert any(x["id"] == ident for x in files.json()), "le ticket entre dans sa file"


@pytest.mark.parametrize("module", MODULES)
async def test_un_contributeur_de_ticket_importe_ne_le_modifie_pas(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    """Il suit, il commente, mais l'import du lendemain reste la seule source d'état."""
    ident, admin, agent = await _ticket(session, module, f"contribro-{module}")
    await client.post(
        f"/{module}/{ident}/contributeurs", headers=entetes(admin), json={"utilisateur_id": agent}
    )

    r = await client.post(
        f"/{module}/{ident}/transition", headers=entetes(agent), json={"vers": "Résolu"}
    )

    assert r.status_code == 404, r.text


@pytest.mark.parametrize("module", MODULES)
async def test_aucune_creation_manuelle(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    _, admin, _ = await _ticket(session, module, f"creer-{module}")

    r = await client.post(
        f"/{module}",
        headers=entetes(admin),
        json={"titre": "Ticket inventé", "impact": 3, "urgence": 3},
    )

    assert r.status_code == 405, r.text


# --- Ce qui reste : observer, et parler entre nous ------------------------------------------------


@pytest.mark.parametrize("module", MODULES)
async def test_la_liste_et_la_fiche_restent_lisibles(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    ident, _, agent = await _ticket(session, module, f"lire-{module}")

    assert (await client.get(f"/{module}", headers=entetes(agent))).status_code == 200
    detail = await client.get(f"/{module}/{ident}", headers=entetes(agent))
    assert detail.status_code == 200, detail.text
    assert "historique" in detail.json(), "le parcours du ticket reste consultable"


@pytest.mark.parametrize("module", MODULES)
async def test_la_discussion_interne_reste_ouverte(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    """Nos échanges nous appartiennent : ils ne viennent pas du fichier."""
    ident, _, agent = await _ticket(session, module, f"discu-{module}")

    r = await client.post(
        f"/commentaires/{ident}",
        headers=entetes(agent),
        json={"texte": "Vu avec l'équipe réseau."},
    )

    assert r.status_code == 201, r.text


@pytest.mark.parametrize("module", MODULES)
async def test_l_export_reste_disponible(
    client: AsyncClient, session: AsyncSession, module: str
) -> None:
    """L'analyse est la raison d'être de ces deux modules."""
    _, _, agent = await _ticket(session, module, f"export-{module}")

    r = await client.get(f"/{module}/export?format=csv", headers=entetes(agent))

    assert r.status_code == 200, r.text


async def test_les_pieces_jointes_d_un_incident_restent_consultables(
    client: AsyncClient, session: AsyncSession
) -> None:
    ident, _, agent = await _ticket(session, "incidents", "docs")

    r = await client.get(f"/incidents/{ident}/documents", headers=entetes(agent))

    assert r.status_code == 200, r.text


# --- Le reste de la plateforme n'est pas touché --------------------------------------------------


async def test_un_changement_reste_pilotable(client: AsyncClient, session: AsyncSession) -> None:
    """La lecture seule ne vaut que pour les tickets importés."""
    responsable = await creer_utilisateur(session, email="resp.chg@afgbank.ml")
    changement = await creer_activite(
        session, module="changement", reference="CHG-RO-1", responsable_id=responsable
    )

    r = await client.post(
        f"/changements/{changement}/transition",
        headers=entetes(responsable),
        json={"vers": "Soumis"},
    )

    assert r.status_code == 200, r.text


async def test_un_incident_n_expose_pas_les_documents_de_tache(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un incident n'a pas de tâches : la route vers leurs pièces jointes ne doit pas exister.

    Elle a survécu au passage en lecture seule, alors que la création de tâches, elle, a disparu.
    """
    ident, admin, _ = await _ticket(session, "incidents", "doctache")

    r = await client.get(
        f"/incidents/{ident}/taches/{ident}/documents", headers=entetes(admin)
    )

    assert r.status_code == 404, r.text


async def test_un_changement_expose_les_documents_de_tache(
    client: AsyncClient, session: AsyncSession
) -> None:
    """La route existe là où les tâches existent : une tâche inconnue répond 404, pas la route."""
    responsable = await creer_utilisateur(session, email="resp.doctache@afgbank.ml")
    changement = await creer_activite(
        session, module="changement", reference="CHG-DOC-1", responsable_id=responsable
    )

    r = await client.post(
        f"/changements/{changement}/taches",
        headers=entetes(responsable),
        json={"titre": "Déployer"},
    )
    assert r.status_code in (200, 201), r.text
    tache = await session.scalar(
        text("SELECT id::text FROM core.tache WHERE activite_id = cast(:a as uuid)"),
        {"a": changement},
    )

    r = await client.get(
        f"/changements/{changement}/taches/{tache}/documents", headers=entetes(responsable)
    )
    assert r.status_code == 200, r.text

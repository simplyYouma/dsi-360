"""Le type de projet : vocabulaire enrichi à la volée, et le déroulé qu'il apporte.

Un type porte les jalons habituels de sa nature. À la création d'un projet, ils sont **recopiés** :
le projet les possède ensuite et les modifie librement. Retoucher le modèle ne rejoue pas
l'histoire des projets déjà ouverts.
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _admin(session: AsyncSession, suffixe: str) -> str:
    return await creer_utilisateur(session, email=f"admin.{suffixe}@afgbank.ml", profil="ADMIN")


async def test_le_libelle_saisi_est_reecrit_proprement(
    client: AsyncClient, session: AsyncSession
) -> None:
    """« migration   de   données » ne doit pas entrer tel quel dans le référentiel."""
    admin = await _admin(session, "type-propre")

    r = await client.post(
        "/projets/types",
        headers=entetes(admin),
        json={"libelle": "  migration   de   données  "},
    )

    assert r.status_code == 201, r.text
    assert r.json()["libelle"] == "Migration de données"
    assert r.json()["code"] == "MIGRATION_DE_DONNEES"


async def test_le_meme_type_saisi_deux_fois_n_en_fait_qu_un(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _admin(session, "type-doublon")

    premier = await client.post(
        "/projets/types", headers=entetes(admin), json={"libelle": "Refonte poste de travail"}
    )
    second = await client.post(
        "/projets/types", headers=entetes(admin), json={"libelle": "refonte POSTE de travail"}
    )

    assert premier.status_code == 201, premier.text
    assert second.status_code == 201, second.text
    assert premier.json()["id"] == second.json()["id"]


async def test_le_type_pose_ses_jalons_a_la_creation_du_projet(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _admin(session, "type-jalons")
    type_projet = (
        await client.post(
            "/projets/types", headers=entetes(admin), json={"libelle": "Ouverture d'agence"}
        )
    ).json()
    for titre in ("Étude du site", "Câblage", "Recette"):
        r = await client.post(
            f"/projets/types/{type_projet['id']}/jalons",
            headers=entetes(admin),
            json={"titre": titre},
        )
        assert r.status_code == 201, r.text

    projet = (
        await client.post(
            "/projets",
            headers=entetes(admin),
            json={"titre": "Agence de Kati", "categorie_id": type_projet["id"]},
        )
    ).json()
    jalons = (
        await client.get(f"/projets/{projet['id']}/jalons", headers=entetes(admin))
    ).json()

    assert [j["titre"] for j in jalons] == ["Étude du site", "Câblage", "Recette"]
    assert all(j["atteint"] is False for j in jalons)


async def test_changer_le_type_n_ecrase_pas_les_jalons_deja_posés(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le modèle n'est qu'un point de départ : ce que le chef de projet a écrit fait foi."""
    admin = await _admin(session, "type-nonecrase")
    premier = (
        await client.post("/projets/types", headers=entetes(admin), json={"libelle": "Type A"})
    ).json()
    await client.post(
        f"/projets/types/{premier['id']}/jalons", headers=entetes(admin), json={"titre": "Étape A"}
    )
    second = (
        await client.post("/projets/types", headers=entetes(admin), json={"libelle": "Type B"})
    ).json()
    await client.post(
        f"/projets/types/{second['id']}/jalons", headers=entetes(admin), json={"titre": "Étape B"}
    )

    projet = (
        await client.post(
            "/projets",
            headers=entetes(admin),
            json={"titre": "Projet à deux types", "categorie_id": premier["id"]},
        )
    ).json()
    await client.patch(
        f"/projets/{projet['id']}", headers=entetes(admin), json={"categorie_id": second["id"]}
    )
    jalons = (
        await client.get(f"/projets/{projet['id']}/jalons", headers=entetes(admin))
    ).json()

    assert [j["titre"] for j in jalons] == ["Étape A"]


async def test_un_type_porte_par_un_projet_ne_se_retire_plus(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _admin(session, "type-utilise")
    type_projet = (
        await client.post("/projets/types", headers=entetes(admin), json={"libelle": "Type tenu"})
    ).json()
    await client.post(
        "/projets",
        headers=entetes(admin),
        json={"titre": "Projet qui tient le type", "categorie_id": type_projet["id"]},
    )

    r = await client.delete(f"/projets/types/{type_projet['id']}", headers=entetes(admin))

    assert r.status_code == 409, r.text
    assert (
        await session.scalar(
            text("SELECT count(*) FROM core.categorie WHERE id = cast(:id as uuid)"),
            {"id": type_projet["id"]},
        )
        == 1
    )


async def test_un_type_inconnu_est_refuse(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _admin(session, "type-inconnu")

    r = await client.post(
        "/projets",
        headers=entetes(admin),
        json={
            "titre": "Projet au type forgé",
            "categorie_id": "00000000-0000-0000-0000-000000000000",
        },
    )

    assert r.status_code == 422, r.text

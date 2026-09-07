"""Départements : paramétrage, et ce qu'on refuse de casser.

Le département subdivise une direction. Il ORGANISE — il range les dossiers, il alimente les
analyses, il filtre les profils au moment de créer un compte. Il ne cloisonne AUCUN accès : le
périmètre de sécurité reste la direction. C'est pourquoi rien ici ne teste de la visibilité.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _admin(session: AsyncSession, email: str) -> str:
    return await creer_utilisateur(session, email=email, profil="ADMIN")


async def _departements(client: AsyncClient, uid: str) -> list[dict[str, Any]]:
    r = await client.get("/admin/departements", headers=entetes(uid))
    assert r.status_code == 200, r.text
    return list(r.json())


async def test_les_deux_departements_de_la_dsi_existent(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Posés par la migration : sans eux la fonction serait inerte au premier démarrage."""
    admin = await _admin(session, "admin.dep1@afgbank.ml")
    libelles = {d["libelle"] for d in await _departements(client, admin)}
    assert {"Production et Applicatif", "Réseau et Infrastructure"} <= libelles


async def test_creer_renommer_supprimer_un_departement(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _admin(session, "admin.dep2@afgbank.ml")

    r = await client.post(
        "/admin/departements", headers=entetes(admin), json={"libelle": "Études et Projets"}
    )
    assert r.status_code == 201, r.text
    cree = r.json()
    # Le code technique est dérivé du libellé : l'administrateur nomme, il ne code pas.
    assert cree["code"] == "ETUDES_ET_PROJETS"
    assert cree["direction"] == "DSI"
    assert cree["nb_profils"] == 0

    r = await client.patch(
        f"/admin/departements/{cree['id']}",
        headers=entetes(admin),
        json={"libelle": "Études, Projets et Méthodes"},
    )
    assert r.status_code == 200, r.text
    # Renommer ne change pas le code : c'est à lui que les profils sont rattachés.
    assert r.json()["code"] == "ETUDES_ET_PROJETS"
    assert r.json()["libelle"] == "Études, Projets et Méthodes"

    r = await client.delete(f"/admin/departements/{cree['id']}", headers=entetes(admin))
    assert r.status_code == 204, r.text
    assert cree["id"] not in {d["id"] for d in await _departements(client, admin)}


async def test_un_departement_en_double_est_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Casse et espaces ignorés : « production et applicatif » est le même département."""
    admin = await _admin(session, "admin.dep3@afgbank.ml")
    r = await client.post(
        "/admin/departements",
        headers=entetes(admin),
        json={"libelle": "  production et applicatif "},
    )
    assert r.status_code == 409, r.text


async def test_on_ne_supprime_pas_un_departement_qui_porte_des_profils(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le message dit combien, pour qu'on sache quoi faire avant de réessayer."""
    admin = await _admin(session, "admin.dep4@afgbank.ml")
    production = next(
        d for d in await _departements(client, admin) if d["code"] == "PRODUCTION_APPLICATIF"
    )
    assert production["nb_profils"] >= 1

    r = await client.delete(f"/admin/departements/{production['id']}", headers=entetes(admin))

    assert r.status_code == 409, r.text
    assert "profil" in r.json()["detail"]


async def test_les_profils_portent_leur_departement_et_se_filtrent_par_direction(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Choisir une direction charge ses profils — et garde toujours les transverses.

    Sans cette exception, `ADMIN` disparaîtrait du formulaire de création de compte : il
    n'appartient à aucun département, donc à aucune direction, et plus personne ne pourrait
    nommer d'administrateur.
    """
    admin = await _admin(session, "admin.dep5@afgbank.ml")

    r = await client.get("/admin/profils", headers=entetes(admin))
    assert r.status_code == 200, r.text
    par_code = {p["code"]: p for p in r.json()}
    assert par_code["SUPPORT_APP"]["departement"] == "Production et Applicatif"
    assert par_code["RESEAU_TELECOM"]["departement"] == "Réseau et Infrastructure"
    assert par_code["ADMIN"]["departement"] is None

    filtres = await client.get("/admin/profils?direction=DSI", headers=entetes(admin))
    assert filtres.status_code == 200, filtres.text
    codes = {p["code"] for p in filtres.json()}
    assert "ADMIN" in codes, "un profil transverse reste toujours proposable"
    assert "SUPPORT_APP" in codes

    aucune = await client.get("/admin/profils?direction=INEXISTANTE", headers=entetes(admin))
    assert aucune.status_code == 200, aucune.text
    assert {p["code"] for p in aucune.json()} == {"ADMIN"}


async def test_rattacher_un_profil_a_un_departement(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _admin(session, "admin.dep6@afgbank.ml")
    reseau = next(
        d for d in await _departements(client, admin) if d["code"] == "RESEAU_INFRASTRUCTURE"
    )

    r = await client.patch(
        "/admin/profils/SUPPORT_APP",
        headers=entetes(admin),
        json={"libelle": "IT Support Applicatif", "departement_id": reseau["id"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["departement_id"] == reseau["id"]

    # Un PATCH qui ne parle QUE du libellé ne doit pas détacher le profil au passage.
    r = await client.patch(
        "/admin/profils/SUPPORT_APP",
        headers=entetes(admin),
        json={"libelle": "IT Support Applicatif (renommé)"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["departement_id"] == reseau["id"], "le département a été perdu en renommant"

    reste = await session.scalar(
        text("SELECT count(*) FROM core.profil WHERE code = 'SUPPORT_APP'")
    )
    assert reste == 1

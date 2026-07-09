"""Référentiel des profils et directions (cf. ADR-0003).

Cinq profils métier DSI, une seule direction, niveaux de support N1/N2 (la DSI n'a pas de N3 :
le niveau 3 désigne un transfert vers DBS, qui n'a pas de compte dans le système).
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes

PROFILS_ATTENDUS = {
    "ADMIN",
    "SUPPORT_APP_HELPDESK",
    "RESEAU_TELECOM",
    "SYSTEME_RESEAU_TELECOM",
    "SUPPORT_APP",
}

PROFILS_SUPPRIMES = {"DSI", "GESTIONNAIRE", "DG"}


async def test_les_cinq_profils_metier_existent(
    client: AsyncClient, session: AsyncSession
) -> None:
    uid = await creer_utilisateur(session, email="admin.profils@afgbank.ml", profil="ADMIN")

    r = await client.get("/admin/profils", headers=entetes(uid))

    assert r.status_code == 200, r.text
    codes = {p["code"] for p in r.json()}
    assert codes == PROFILS_ATTENDUS


async def test_les_anciens_profils_ont_disparu(client: AsyncClient, session: AsyncSession) -> None:
    uid = await creer_utilisateur(session, email="admin.profils2@afgbank.ml", profil="ADMIN")

    r = await client.get("/admin/profils", headers=entetes(uid))

    codes = {p["code"] for p in r.json()}
    assert codes & PROFILS_SUPPRIMES == set(), "DSI, GESTIONNAIRE et DG sont supprimés (ADR-0003)"


async def test_une_seule_direction_la_dsi(client: AsyncClient, session: AsyncSession) -> None:
    uid = await creer_utilisateur(session, email="admin.dir@afgbank.ml", profil="ADMIN")

    r = await client.get("/admin/directions", headers=entetes(uid))

    assert r.status_code == 200, r.text
    assert [d["code"] for d in r.json()] == ["DSI"]


async def test_seul_l_administrateur_est_transverse(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="a.transverse@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(
        session, email="h.transverse@afgbank.ml", profil="SUPPORT_APP_HELPDESK"
    )

    r_admin = await client.get("/moi", headers=entetes(admin))
    r_agent = await client.get("/moi", headers=entetes(agent))

    assert r_admin.json()["transverse"] is True
    assert r_agent.json()["transverse"] is False


# --- Niveaux de support : la DSI n'a que N1 et N2 ------------------------------------------------


async def test_creation_utilisateur_niveau_3_refusee(
    client: AsyncClient, session: AsyncSession
) -> None:
    """N3 = DBS, hors système : aucun compte DSI ne peut porter ce niveau (ADR-0003 §3)."""
    admin = await creer_utilisateur(session, email="admin.niv@afgbank.ml", profil="ADMIN")

    r = await client.post(
        "/admin/utilisateurs",
        headers=entetes(admin),
        json={
            "email": "niveau3@afgbank.ml",
            "nom": "Niveau",
            "prenom": "Trois",
            "profil_code": "SUPPORT_APP_HELPDESK",
            "direction_code": "DSI",
            "niveau_support": 3,
        },
    )

    assert r.status_code == 422, r.text


async def test_creation_utilisateur_niveau_2_acceptee(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.niv2@afgbank.ml", profil="ADMIN")

    r = await client.post(
        "/admin/utilisateurs",
        headers=entetes(admin),
        json={
            "email": "niveau2@afgbank.ml",
            "nom": "Niveau",
            "prenom": "Deux",
            "profil_code": "RESEAU_TELECOM",
            "direction_code": "DSI",
            "niveau_support": 2,
        },
    )

    assert r.status_code == 201, r.text

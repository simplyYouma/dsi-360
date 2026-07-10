"""Un agent est créé avec son niveau de support. C'est ce qui rend la déduction fiable.

Le niveau d'un ticket importé se lit sur le compte de son gestionnaire (ADR-0005). Un compte sans
niveau ferait retomber son ticket au N1 par défaut, sans que personne ne s'en aperçoive : la
statistique mentirait en silence.

L'administrateur ne traite pas de tickets : il n'a pas de niveau.
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes

BASE = {
    "email": "nouveau@afgbank.ml",
    "nom": "Nouveau",
    "prenom": "Compte",
    "direction_code": "DSI",
}


async def _admin(session: AsyncSession, email: str) -> dict[str, str]:
    return entetes(await creer_utilisateur(session, email=email, profil="ADMIN"))


async def test_un_agent_metier_exige_un_niveau(client: AsyncClient, session: AsyncSession) -> None:
    h = await _admin(session, "admin.niv1@afgbank.ml")

    r = await client.post(
        "/admin/utilisateurs", headers=h, json={**BASE, "profil_code": "RESEAU_TELECOM"}
    )

    assert r.status_code == 422, r.text
    assert "niveau" in r.json()["detail"].lower()


async def test_un_agent_metier_cree_avec_son_niveau(
    client: AsyncClient, session: AsyncSession
) -> None:
    h = await _admin(session, "admin.niv2@afgbank.ml")

    r = await client.post(
        "/admin/utilisateurs",
        headers=h,
        json={**BASE, "profil_code": "RESEAU_TELECOM", "niveau_support": 2},
    )

    assert r.status_code == 201, r.text
    niveau = await session.scalar(
        text("SELECT niveau_support FROM core.utilisateur WHERE email = :e"), {"e": BASE["email"]}
    )
    assert niveau == 2


async def test_l_administrateur_n_a_pas_de_niveau(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Il distribue le travail, il ne traite pas les tickets."""
    h = await _admin(session, "admin.niv3@afgbank.ml")

    r = await client.post(
        "/admin/utilisateurs",
        headers=h,
        json={**BASE, "email": "autre.admin@afgbank.ml", "profil_code": "ADMIN"},
    )

    assert r.status_code == 201, r.text


async def test_on_ne_retire_pas_le_niveau_d_un_agent_metier(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Sinon ses tickets retomberaient au N1 sans que personne ne le voie."""
    h = await _admin(session, "admin.niv4@afgbank.ml")
    agent = await creer_utilisateur(session, email="agent.niv4@afgbank.ml", profil="SUPPORT_APP")

    r = await client.put(
        f"/admin/utilisateurs/{agent}",
        headers=h,
        json={
            "nom": "Agent",
            "prenom": "Métier",
            "profil_code": "SUPPORT_APP",
            "direction_code": "DSI",
            "niveau_support": None,
            "actif": True,
        },
    )

    assert r.status_code == 422, r.text


async def test_promouvoir_un_agent_administrateur_libere_son_niveau(
    client: AsyncClient, session: AsyncSession
) -> None:
    h = await _admin(session, "admin.niv5@afgbank.ml")
    agent = await creer_utilisateur(session, email="agent.niv5@afgbank.ml", profil="SUPPORT_APP")

    r = await client.put(
        f"/admin/utilisateurs/{agent}",
        headers=h,
        json={
            "nom": "Agent",
            "prenom": "Promu",
            "profil_code": "ADMIN",
            "direction_code": "DSI",
            "niveau_support": None,
            "actif": True,
        },
    )

    assert r.status_code == 204, r.text

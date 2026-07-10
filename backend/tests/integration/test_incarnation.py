"""Incarnation d'un compte, pour éprouver les vues par profil — **en développement seulement**.

Un endpoint qui délivre le jeton d'autrui est une porte dérobée. Trois verrous :
l'environnement doit être `dev` (sinon la route n'existe pas : 404, pas 403 — on ne révèle pas
son existence), l'appelant doit être administrateur, et chaque usage est journalisé.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.config import get_settings
from tests.integration.conftest import MOT_DE_PASSE, creer_utilisateur, entetes


@pytest.fixture
def en_production() -> object:
    """Bascule l'environnement le temps d'un test, puis le rétablit."""
    settings = get_settings()
    avant = settings.environnement
    object.__setattr__(settings, "environnement", "prod")
    yield
    object.__setattr__(settings, "environnement", avant)


async def test_l_admin_incarne_un_agent(client: AsyncClient, session: AsyncSession) -> None:
    admin = await creer_utilisateur(session, email="admin.inc@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.inc@afgbank.ml", profil="RESEAU_TELECOM")

    r = await client.post("/auth/incarner", headers=entetes(admin), json={"utilisateur_id": agent})

    assert r.status_code == 200, r.text
    jeton = r.json()["acces"]

    moi = await client.get("/moi", headers={"Authorization": f"Bearer {jeton}"})
    assert moi.status_code == 200
    assert moi.json()["email"] == "agent.inc@afgbank.ml"
    assert moi.json()["profil"] == "RESEAU_TELECOM"


async def test_le_jeton_incarne_porte_les_droits_du_compte_cible(
    client: AsyncClient, session: AsyncSession
) -> None:
    """L'intérêt du dispositif : le serveur répond comme au compte incarné, pas comme à l'admin."""
    admin = await creer_utilisateur(session, email="admin.inc2@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.inc2@afgbank.ml")
    jeton = (
        await client.post("/auth/incarner", headers=entetes(admin), json={"utilisateur_id": agent})
    ).json()["acces"]

    r = await client.get("/admin/utilisateurs", headers={"Authorization": f"Bearer {jeton}"})

    assert r.status_code == 403, "incarné, on n'entre plus dans l'administration"


async def test_un_agent_ne_peut_pas_incarner(client: AsyncClient, session: AsyncSession) -> None:
    agent = await creer_utilisateur(session, email="agent.inc3@afgbank.ml")
    cible = await creer_utilisateur(session, email="cible.inc3@afgbank.ml")

    r = await client.post("/auth/incarner", headers=entetes(agent), json={"utilisateur_id": cible})

    assert r.status_code == 403


async def test_on_n_incarne_pas_un_compte_inactif(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.inc4@afgbank.ml", profil="ADMIN")
    inactif = await creer_utilisateur(session, email="inactif.inc4@afgbank.ml", actif=False)

    r = await client.post(
        "/auth/incarner", headers=entetes(admin), json={"utilisateur_id": inactif}
    )

    assert r.status_code == 404


async def test_l_incarnation_est_journalisee(client: AsyncClient, session: AsyncSession) -> None:
    admin = await creer_utilisateur(session, email="admin.inc5@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.inc5@afgbank.ml")

    await client.post("/auth/incarner", headers=entetes(admin), json={"utilisateur_id": agent})

    journal = (await client.get("/admin/journal?page=1", headers=entetes(admin))).json()
    traces = [e for e in journal["elements"] if e["action"] == "INCARNATION"]
    assert traces, "prendre l'identité d'autrui laisse une trace"


async def test_la_route_n_existe_pas_hors_developpement(
    client: AsyncClient, session: AsyncSession, en_production: object
) -> None:
    """404 et non 403 : on ne révèle pas l'existence d'une porte qu'on n'ouvre pas."""
    admin = await creer_utilisateur(session, email="admin.inc6@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.inc6@afgbank.ml")

    r = await client.post("/auth/incarner", headers=entetes(admin), json={"utilisateur_id": agent})

    assert r.status_code == 404, r.text


async def test_moi_expose_l_environnement(client: AsyncClient, session: AsyncSession) -> None:
    """Le front ne peut pas deviner s'il tourne en dev : un build de prod servi ici mentirait."""
    uid = await creer_utilisateur(session, email="env.inc@afgbank.ml")

    r = await client.get("/moi", headers=entetes(uid))

    assert r.status_code == 200, r.text
    assert r.json()["environnement"] == "dev"


# --- Incarner, c'est regarder ses écrans, pas devenir cette personne ------------------------------


async def _incarner(client: AsyncClient, admin: str, cible: str) -> dict[str, str]:
    r = await client.post("/auth/incarner", headers=entetes(admin), json={"utilisateur_id": cible})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['acces']}"}


async def test_moi_dit_qui_incarne(client: AsyncClient, session: AsyncSession) -> None:
    """Le front ne peut pas le deviner ; le serveur le dit."""
    admin = await creer_utilisateur(session, email="admin.dit@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.dit@afgbank.ml")

    h = await _incarner(client, admin, agent)
    moi = (await client.get("/moi", headers=h)).json()

    assert moi["incarne_par"] == "admin.dit@afgbank.ml"


async def test_moi_sans_incarnation_ne_dit_personne(
    client: AsyncClient, session: AsyncSession
) -> None:
    agent = await creer_utilisateur(session, email="agent.seul@afgbank.ml")

    moi = (await client.get("/moi", headers=entetes(agent))).json()

    assert moi["incarne_par"] is None


async def test_on_ne_change_pas_le_mot_de_passe_de_celui_qu_on_incarne(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Éprouver les vues d'un agent ne donne aucun droit sur ses secrets."""
    admin = await creer_utilisateur(session, email="admin.mdp@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.mdp@afgbank.ml")

    h = await _incarner(client, admin, agent)
    r = await client.post(
        "/auth/mot-de-passe",
        headers=h,
        json={"ancien": MOT_DE_PASSE, "nouveau": "UnAutreMotDePasse1"},
    )

    assert r.status_code == 403, r.text


async def test_on_ne_change_pas_son_mot_de_passe_en_incarnant(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un agent, lui, change bien le sien."""
    agent = await creer_utilisateur(session, email="agent.sienmdp@afgbank.ml")

    r = await client.post(
        "/auth/mot-de-passe",
        headers=entetes(agent),
        json={"ancien": MOT_DE_PASSE, "nouveau": "UnAutreMotDePasse1"},
    )

    assert r.status_code == 204, r.text


async def test_on_n_incarne_pas_depuis_une_incarnation(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Sinon la trace d'audit désignerait le mauvais responsable."""
    admin = await creer_utilisateur(session, email="admin.chaine@afgbank.ml", profil="ADMIN")
    autre = await creer_utilisateur(session, email="autre.chaine@afgbank.ml", profil="ADMIN")
    cible = await creer_utilisateur(session, email="cible.chaine@afgbank.ml")

    h = await _incarner(client, admin, autre)
    r = await client.post("/auth/incarner", headers=h, json={"utilisateur_id": cible})

    assert r.status_code == 403, r.text


async def test_le_rafraichissement_conserve_l_incarnation(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Sinon, au bout de 15 minutes, l'admin redeviendrait lui-même sans le savoir."""
    admin = await creer_utilisateur(session, email="admin.refr@afgbank.ml", profil="ADMIN")
    agent = await creer_utilisateur(session, email="agent.refr@afgbank.ml")

    r = await client.post("/auth/incarner", headers=entetes(admin), json={"utilisateur_id": agent})
    refresh = r.json()["refresh"]

    r = await client.post("/auth/refresh", json={"refresh": refresh})
    assert r.status_code == 200, r.text
    entete = {"Authorization": f"Bearer {r.json()['acces']}"}
    moi = (await client.get("/moi", headers=entete)).json()

    assert moi["email"] == "agent.refr@afgbank.ml"
    assert moi["incarne_par"] == "admin.refr@afgbank.ml"

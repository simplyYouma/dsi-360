"""Préférences de notification : elles suivent le compte, pas le navigateur.

Le carillon était réglé en stockage local : un agent changeant de poste retrouvait le réglage par
défaut, et rien ne le suivait. Rattaché au compte, il vaut partout où la personne se connecte.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def test_les_preferences_par_defaut_activent_les_canaux_utiles(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Sans réglage enregistré, tout ce qui sert est actif : une notification doit se voir."""
    agent = await creer_utilisateur(session, email="pref.defaut@afgbank.ml")

    r = await client.get("/notifications/preferences", headers=entetes(agent))

    assert r.status_code == 200, r.text
    assert r.json() == {
        "interne": True,
        "email": True,
        "son": True,
        "teams": False,
        "whatsapp": False,
    }


async def test_couper_le_son_est_conserve(client: AsyncClient, session: AsyncSession) -> None:
    """Le réglage survit à la déconnexion : c'est tout l'intérêt de le porter côté serveur."""
    agent = await creer_utilisateur(session, email="pref.son@afgbank.ml")

    r = await client.put(
        "/notifications/preferences",
        json={"interne": True, "email": True, "son": False, "teams": False, "whatsapp": False},
        headers=entetes(agent),
    )
    assert r.status_code == 204, r.text

    relu = await client.get("/notifications/preferences", headers=entetes(agent))
    assert relu.status_code == 200, relu.text
    assert relu.json()["son"] is False
    assert relu.json()["email"] is True, "couper le son ne coupe pas l'e-mail"


async def test_les_preferences_sont_propres_a_chacun(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le réglage de l'un n'impose rien à l'autre."""
    silencieux = await creer_utilisateur(session, email="pref.muet@afgbank.ml")
    autre = await creer_utilisateur(session, email="pref.autre@afgbank.ml")

    await client.put(
        "/notifications/preferences",
        json={"interne": True, "email": True, "son": False, "teams": False, "whatsapp": False},
        headers=entetes(silencieux),
    )

    r = await client.get("/notifications/preferences", headers=entetes(autre))
    assert r.json()["son"] is True

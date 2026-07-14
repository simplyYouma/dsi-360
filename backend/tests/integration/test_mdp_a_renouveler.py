"""Tant que le mot de passe n'est pas renouvelé, le serveur ferme l'application.

Le compte administrateur initial est semé avec le mot de passe du `.env` — connu de l'exploitant.
Sans garde **côté serveur**, ce mot de passe resterait un accès complet et permanent à l'API : il
suffirait d'appeler les routes directement (curl, Postman) pour contourner la redirection de
l'écran. On vérifie donc que le refus vient du serveur, pas de l'interface.

On vérifie aussi qu'un module inconnu est bien une erreur du client (404), pas une panne (500).
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import MOT_DE_PASSE, creer_utilisateur, entetes


async def _exiger_renouvellement(session: AsyncSession, utilisateur_id: str) -> None:
    await session.execute(
        text("UPDATE core.utilisateur SET doit_changer_mdp = true WHERE id = cast(:id as uuid)"),
        {"id": utilisateur_id},
    )
    await session.commit()


async def test_mdp_a_renouveler_ferme_l_application(
    client: AsyncClient, session: AsyncSession
) -> None:
    uid = await creer_utilisateur(session, email="renouveler@afgbank.ml")
    await _exiger_renouvellement(session, uid)

    # Toute route applicative est refusée — même avec un jeton parfaitement valide.
    r = await client.get("/referentiels/etats?module=incident", headers=entetes(uid))
    assert r.status_code == 403, r.text

    # Mais on doit pouvoir lire son profil : l'écran a besoin du drapeau pour rediriger.
    r = await client.get("/moi", headers=entetes(uid))
    assert r.status_code == 200, r.text
    assert r.json()["doit_changer_mdp"] is True

    # Et changer son mot de passe, évidemment — sinon le compte serait muré.
    r = await client.post(
        "/auth/mot-de-passe",
        headers=entetes(uid),
        json={"ancien": MOT_DE_PASSE, "nouveau": "NouveauMotDePasse1"},
    )
    assert r.status_code == 204, r.text

    # Une fois renouvelé, l'application s'ouvre.
    r = await client.get("/referentiels/etats?module=incident", headers=entetes(uid))
    assert r.status_code == 200, r.text


async def test_module_inconnu_est_un_404_pas_un_500(
    client: AsyncClient, session: AsyncSession
) -> None:
    uid = await creer_utilisateur(session, email="etats@afgbank.ml")

    r = await client.get("/referentiels/etats?module=inconnu", headers=entetes(uid))
    assert r.status_code == 404, r.text

    r = await client.get("/referentiels/etats?module=changement", headers=entetes(uid))
    assert r.status_code == 200, r.text
    assert "CAB" in r.json()

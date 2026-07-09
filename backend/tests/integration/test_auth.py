"""Authentification : identifiants, blocage, expiration, jetons.

Le point critique (cf. docs/04-SECURITY) : bloquer ou expirer un compte coupe l'accès
**immédiatement**, même si un jeton d'accès encore valide circule.
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import MOT_DE_PASSE, creer_utilisateur, entetes


async def test_login_identifiants_valides(client: AsyncClient, session: AsyncSession) -> None:
    await creer_utilisateur(session, email="valide@afgbank.ml")

    r = await client.post(
        "/auth/login", json={"email": "valide@afgbank.ml", "mot_de_passe": MOT_DE_PASSE}
    )

    assert r.status_code == 200, r.text
    assert r.json()["acces"]


async def test_login_mauvais_mot_de_passe(client: AsyncClient, session: AsyncSession) -> None:
    await creer_utilisateur(session, email="mauvais@afgbank.ml")

    r = await client.post(
        "/auth/login", json={"email": "mauvais@afgbank.ml", "mot_de_passe": "PasLeBon1"}
    )

    assert r.status_code == 401


async def test_login_email_inconnu(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/login", json={"email": "fantome@afgbank.ml", "mot_de_passe": MOT_DE_PASSE}
    )

    assert r.status_code == 401


async def test_moi_sans_jeton_refuse(client: AsyncClient) -> None:
    assert (await client.get("/moi")).status_code == 401


async def test_moi_jeton_invalide_refuse(client: AsyncClient) -> None:
    r = await client.get("/moi", headers={"Authorization": "Bearer pas-un-jeton"})

    assert r.status_code == 401


async def test_jeton_de_rafraichissement_refuse_comme_jeton_d_acces(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un jeton de type « refresh » ne doit jamais ouvrir une route protégée."""
    from dsi360.infrastructure.securite import creer_jeton

    uid = await creer_utilisateur(session, email="refresh@afgbank.ml")
    jeton = creer_jeton(uid, "refresh")

    r = await client.get("/moi", headers={"Authorization": f"Bearer {jeton}"})

    assert r.status_code == 401


async def test_compte_bloque_coupe_l_acces_malgre_un_jeton_valide(
    client: AsyncClient, session: AsyncSession
) -> None:
    uid = await creer_utilisateur(session, email="bloque@afgbank.ml", actif=False)

    r = await client.get("/moi", headers=entetes(uid))

    assert r.status_code == 401


async def test_compte_expire_coupe_l_acces_malgre_un_jeton_valide(
    client: AsyncClient, session: AsyncSession
) -> None:
    hier = datetime.now(UTC) - timedelta(days=1)
    uid = await creer_utilisateur(session, email="expire@afgbank.ml", expire_le=hier)

    r = await client.get("/moi", headers=entetes(uid))

    assert r.status_code == 401


async def test_compte_expirant_demain_reste_actif(
    client: AsyncClient, session: AsyncSession
) -> None:
    demain = datetime.now(UTC) + timedelta(days=1)
    uid = await creer_utilisateur(session, email="temporaire@afgbank.ml", expire_le=demain)

    r = await client.get("/moi", headers=entetes(uid))

    assert r.status_code == 200, r.text
    assert r.json()["email"] == "temporaire@afgbank.ml"


async def test_login_refuse_un_compte_bloque(client: AsyncClient, session: AsyncSession) -> None:
    await creer_utilisateur(session, email="bloque2@afgbank.ml", actif=False)

    r = await client.post(
        "/auth/login", json={"email": "bloque2@afgbank.ml", "mot_de_passe": MOT_DE_PASSE}
    )

    assert r.status_code == 401

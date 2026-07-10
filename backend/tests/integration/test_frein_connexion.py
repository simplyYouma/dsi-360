"""Un mot de passe ne se devine pas en boucle : la porte se ferme après quelques essais.

Sans ce frein, rien n'empêche d'essayer des mots de passe indéfiniment — et le MFA posé au-dessus
d'une porte qu'on peut marteler ne protégerait pas davantage.

Le verrou est **temporaire** : verrouiller un compte pour toujours donnerait à un attaquant le
pouvoir d'exclure n'importe qui du système.
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.config import get_settings
from tests.integration.conftest import MOT_DE_PASSE, creer_utilisateur

MAUVAIS = "PasLeBonMotDePasse1"


async def _echouer(client: AsyncClient, email: str, fois: int) -> int:
    """Enchaîne `fois` tentatives ratées ; renvoie le dernier code de réponse."""
    code = 0
    for _ in range(fois):
        r = await client.post("/auth/login", json={"email": email, "mot_de_passe": MAUVAIS})
        code = r.status_code
    return code


async def _echecs_en_base(session: AsyncSession, email: str) -> int:
    valeur = await session.scalar(
        text("SELECT echecs_connexion FROM core.utilisateur WHERE email = :e"), {"e": email}
    )
    return int(valeur)


async def test_quelques_echecs_ne_ferment_pas_la_porte(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un agent qui se trompe deux fois doit pouvoir entrer à la troisième."""
    email = "frein.doux@afgbank.ml"
    await creer_utilisateur(session, email=email)
    maxi = get_settings().login_echecs_max

    assert await _echouer(client, email, maxi - 1) == 401

    r = await client.post("/auth/login", json={"email": email, "mot_de_passe": MOT_DE_PASSE})
    assert r.status_code == 200, r.text


async def test_le_succes_remet_le_compteur_a_zero(
    client: AsyncClient, session: AsyncSession
) -> None:
    email = "frein.remise@afgbank.ml"
    await creer_utilisateur(session, email=email)

    await _echouer(client, email, get_settings().login_echecs_max - 1)
    await client.post("/auth/login", json={"email": email, "mot_de_passe": MOT_DE_PASSE})

    assert await _echecs_en_base(session, email) == 0


async def test_trop_d_echecs_verrouillent_le_compte(
    client: AsyncClient, session: AsyncSession
) -> None:
    email = "frein.verrou@afgbank.ml"
    await creer_utilisateur(session, email=email)

    await _echouer(client, email, get_settings().login_echecs_max)

    r = await client.post("/auth/login", json={"email": email, "mot_de_passe": MOT_DE_PASSE})
    assert r.status_code == 429, "le verrou prime, même avec le bon mot de passe"
    assert "Retry-After" in r.headers


async def test_le_verrou_expire_de_lui_meme(client: AsyncClient, session: AsyncSession) -> None:
    """Sinon un attaquant exclurait n'importe qui du système en se trompant exprès."""
    email = "frein.expire@afgbank.ml"
    await creer_utilisateur(session, email=email)
    await _echouer(client, email, get_settings().login_echecs_max)

    await session.execute(
        text("UPDATE core.utilisateur SET verrouille_jusqu_a = :t WHERE email = :e"),
        {"t": datetime.now(UTC) - timedelta(seconds=1), "e": email},
    )

    r = await client.post("/auth/login", json={"email": email, "mot_de_passe": MOT_DE_PASSE})
    assert r.status_code == 200, r.text

    verrou = await session.scalar(
        text("SELECT verrouille_jusqu_a FROM core.utilisateur WHERE email = :e"), {"e": email}
    )
    assert verrou is None, "une connexion réussie efface le verrou expiré"


async def test_un_email_inconnu_ne_revele_rien(client: AsyncClient) -> None:
    """Ni verrou, ni message différent : le 401 ne dit pas si le compte existe."""
    r = await client.post(
        "/auth/login", json={"email": "fantome@afgbank.ml", "mot_de_passe": MAUVAIS}
    )

    assert r.status_code == 401
    assert r.json()["detail"] == "Identifiants invalides."


async def test_les_tentatives_sont_journalisees(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un compte martelé doit se voir dans le journal d'audit."""
    email = "frein.audit@afgbank.ml"
    await creer_utilisateur(session, email=email)

    await _echouer(client, email, get_settings().login_echecs_max)
    await client.post("/auth/login", json={"email": email, "mot_de_passe": MOT_DE_PASSE})

    actions = (
        await session.execute(
            text(
                "SELECT action FROM audit.journal WHERE acteur_email = :e "
                "AND action IN ('CONNEXION_ECHOUEE', 'CONNEXION_BLOQUEE')"
            ),
            {"e": email},
        )
    ).scalars().all()

    assert actions.count("CONNEXION_ECHOUEE") == get_settings().login_echecs_max
    assert "CONNEXION_BLOQUEE" in actions

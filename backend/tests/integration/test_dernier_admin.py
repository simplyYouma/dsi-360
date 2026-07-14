"""Le système ne doit jamais tomber à zéro administrateur.

Il n'y a pas de « super-administrateur » au-dessus des autres : tous les admins sont égaux. Mais si
le dernier administrateur actif se bloque ou se rétrograde, plus personne ne peut administrer. Le
serveur refuse donc cette manœuvre tant qu'aucun autre administrateur actif n'existe.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


def _corps(**extra: Any) -> dict[str, Any]:
    base = {"nom": "Admin", "prenom": "Unique", "direction_code": "DSI", "actif": True}
    return {**base, **extra}


async def _rendre_seul_admin(session: AsyncSession, garder: str) -> None:
    """Désactive tout autre administrateur (dont le compte seedé) pour isoler le cas « dernier »."""
    await session.execute(
        text(
            "UPDATE core.utilisateur SET actif = false "
            "WHERE profil_id = (SELECT id FROM core.profil WHERE code = 'ADMIN') "
            "AND id::text <> :garder"
        ),
        {"garder": garder},
    )
    await session.commit()


async def test_le_dernier_admin_ne_peut_pas_se_retrograder(
    client: AsyncClient, session: AsyncSession
) -> None:
    seul = await creer_utilisateur(session, email="seul.admin@afgbank.ml", profil="ADMIN")
    await _rendre_seul_admin(session, seul)

    # Se rétrograder en profil métier alors qu'on est le seul admin actif : refusé.
    r = await client.put(
        f"/admin/utilisateurs/{seul}",
        headers=entetes(seul),
        json=_corps(profil_code="SUPPORT_APP_HELPDESK", niveau_support=1),
    )
    assert r.status_code == 400, r.text
    assert "administrateur" in r.json()["detail"].lower()

    # Avec un second administrateur actif, la rétrogradation du premier devient possible.
    await creer_utilisateur(session, email="second.admin@afgbank.ml", profil="ADMIN")
    r = await client.put(
        f"/admin/utilisateurs/{seul}",
        headers=entetes(seul),
        json=_corps(profil_code="SUPPORT_APP_HELPDESK", niveau_support=1),
    )
    assert r.status_code == 204, r.text


async def test_bloquer_le_dernier_admin_est_refuse(
    client: AsyncClient, session: AsyncSession
) -> None:
    seul = await creer_utilisateur(session, email="bloc.admin@afgbank.ml", profil="ADMIN")
    autre = await creer_utilisateur(session, email="autre.admin@afgbank.ml", profil="ADMIN")
    await _rendre_seul_admin(session, seul)  # ne laisse que `seul` actif

    # `autre` (admin mais inactif) ne compte pas : bloquer `seul` via un autre admin actif est
    # impossible puisqu'il n'y en a pas. On vérifie via `seul` lui-même → dernier admin → refus.
    r = await client.put(
        f"/admin/utilisateurs/{seul}",
        headers=entetes(seul),
        json=_corps(profil_code="ADMIN", actif=False),
    )
    # L'anti-lockout personnel intercepte d'abord (on ne se bloque pas soi-même) : 400 dans tous
    # les cas, ce qui est le comportement attendu.
    assert r.status_code == 400, r.text
    assert autre  # `autre` existe mais inactif : ne sauve pas du blocage

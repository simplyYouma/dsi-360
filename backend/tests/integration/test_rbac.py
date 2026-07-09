"""RBAC : la matrice d'accès par profil est appliquée **côté serveur**, sur chaque route.

Cf. CLAUDE.md §6.3 (« tout accès vérifié côté serveur, jamais seulement à l'écran ») et
config/acces.py pour la matrice de référence.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes

# (profil, chemin, statut attendu) — dérivé de ACCES_PAR_PROFIL_DEFAUT (cf. ADR-0003).
CAS_ACCES = [
    # L'administrateur atteint tout, lui seul entre dans l'administration.
    ("ADMIN", "/incidents", 200),
    ("ADMIN", "/admin/utilisateurs", 200),
    # Les profils métier traitent l'opérationnel, jamais l'administration.
    ("SUPPORT_APP_HELPDESK", "/incidents", 200),
    ("SUPPORT_APP_HELPDESK", "/demandes", 200),
    ("SUPPORT_APP_HELPDESK", "/admin/utilisateurs", 403),
    ("RESEAU_TELECOM", "/incidents", 200),
    ("RESEAU_TELECOM", "/admin/utilisateurs", 403),
    ("SYSTEME_RESEAU_TELECOM", "/incidents", 200),
    ("SYSTEME_RESEAU_TELECOM", "/admin/utilisateurs", 403),
    ("SUPPORT_APP", "/changements", 200),
    ("SUPPORT_APP", "/admin/utilisateurs", 403),
]


@pytest.mark.parametrize(("profil", "chemin", "attendu"), CAS_ACCES)
async def test_matrice_acces_par_profil(
    client: AsyncClient, session: AsyncSession, profil: str, chemin: str, attendu: int
) -> None:
    uid = await creer_utilisateur(session, email=f"{profil.lower()}.rbac@afgbank.ml", profil=profil)

    r = await client.get(chemin, headers=entetes(uid))

    assert r.status_code == attendu, f"{profil} sur {chemin} : {r.status_code} ({r.text[:120]})"


@pytest.mark.parametrize("chemin", ["/incidents", "/demandes", "/admin/utilisateurs", "/projets"])
async def test_aucune_route_protegee_sans_jeton(client: AsyncClient, chemin: str) -> None:
    """Sans jeton, aucune route métier ne répond — jamais de fuite par défaut."""
    assert (await client.get(chemin)).status_code == 401


async def test_un_agent_metier_ne_peut_pas_creer_d_utilisateur(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le contrôle est côté serveur : masquer le bouton ne suffirait pas."""
    uid = await creer_utilisateur(
        session, email="agent.escalade@afgbank.ml", profil="SUPPORT_APP_HELPDESK"
    )

    r = await client.post(
        "/admin/utilisateurs",
        headers=entetes(uid),
        json={
            "email": "intrus@afgbank.ml",
            "nom": "Intrus",
            "prenom": "Sans",
            "profil_code": "ADMIN",
            "direction_code": "DSI",
        },
    )

    assert r.status_code == 403, "un corps valide doit être rejeté sur l'accès, pas sur la forme"

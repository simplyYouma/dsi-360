"""RBAC : la matrice d'accès par profil est appliquée **côté serveur**, sur chaque route.

Cf. CLAUDE.md §6.3 (« tout accès vérifié côté serveur, jamais seulement à l'écran ») et
config/acces.py pour la matrice de référence.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes

# (profil, chemin, statut attendu) — dérivé de ACCES_PAR_PROFIL_DEFAUT.
CAS_ACCES = [
    # L'administrateur atteint tout.
    ("ADMIN", "/incidents", 200),
    ("ADMIN", "/admin/utilisateurs", 200),
    # Le DSI a tout sauf l'administration.
    ("DSI", "/incidents", 200),
    ("DSI", "/admin/utilisateurs", 403),
    # Le gestionnaire traite l'opérationnel, jamais l'administration.
    ("GESTIONNAIRE", "/incidents", 200),
    ("GESTIONNAIRE", "/demandes", 200),
    ("GESTIONNAIRE", "/admin/utilisateurs", 403),
    # La DG est en restitution : pas d'incidents ni de demandes, mais gouvernance et risques.
    ("DG", "/incidents", 403),
    ("DG", "/demandes", 403),
    ("DG", "/changements", 403),
    ("DG", "/gouvernance", 200),
    ("DG", "/risques", 200),
    ("DG", "/admin/utilisateurs", 403),
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


async def test_un_gestionnaire_ne_peut_pas_creer_d_utilisateur(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le contrôle est côté serveur : masquer le bouton ne suffirait pas."""
    uid = await creer_utilisateur(session, email="gest.escalade@afgbank.ml", profil="GESTIONNAIRE")

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

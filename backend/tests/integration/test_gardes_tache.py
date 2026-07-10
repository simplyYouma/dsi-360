"""Une tâche assignée : son porteur rend compte, il ne se redistribue pas le travail.

L'assigné d'une tâche n'en change que le **statut**. Ni l'assigné, ni l'échéance, ni le titre :
c'est le gestionnaire, les contributeurs ou l'administrateur qui organisent. Un tiers ne touche
à rien.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, designer, entetes


async def _changement_avec_tache(
    session: AsyncSession, suffixe: str
) -> tuple[str, str, dict[str, str]]:
    """Un changement, une tâche assignée à « porteur », et l'équipe autour."""
    gens = {}
    for role, profil in (
        ("admin", "ADMIN"),
        ("responsable", "SUPPORT_APP_HELPDESK"),
        ("contributeur", "SUPPORT_APP_HELPDESK"),
        ("porteur", "SUPPORT_APP_HELPDESK"),
        ("tiers", "SUPPORT_APP_HELPDESK"),
    ):
        gens[role] = await creer_utilisateur(
            session, email=f"{role}.{suffixe}@afgbank.ml", profil=profil
        )
    changement = await creer_activite(
        session,
        module="changement",
        reference=f"CHG-TCH-{suffixe}",
        responsable_id=gens["responsable"],
    )
    await designer(
        session, activite_id=changement, utilisateur_id=gens["contributeur"], role="CONTRIBUTEUR"
    )
    from sqlalchemy import text

    tache = await session.scalar(
        text(
            "INSERT INTO core.tache (activite_id, titre, statut, assigne_id) "
            "VALUES (cast(:aid as uuid), 'Déployer', 'À faire', cast(:uid as uuid)) "
            "RETURNING id::text"
        ),
        {"aid": changement, "uid": gens["porteur"]},
    )
    await session.commit()
    return changement, str(tache), gens


async def test_l_assigne_change_le_statut_de_sa_tache(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, tache, gens = await _changement_avec_tache(session, "statut")

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(gens["porteur"]),
        json={"statut": "En cours"},
    )

    assert r.status_code == 200, r.text


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [("titre", "Autre titre"), ("echeance", "2026-12-31"), ("description", "Autre chose")],
)
async def test_l_assigne_ne_touche_pas_aux_autres_champs(
    client: AsyncClient, session: AsyncSession, champ: str, valeur: str
) -> None:
    changement, tache, gens = await _changement_avec_tache(session, f"champ-{champ}")

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(gens["porteur"]),
        json={champ: valeur},
    )

    assert r.status_code == 403, f"{champ} : {r.text}"
    assert "statut" in r.json()["detail"]


async def test_l_assigne_ne_se_reassigne_pas_la_tache(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, tache, gens = await _changement_avec_tache(session, "reassigne")

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(gens["porteur"]),
        json={"assigne_id": gens["tiers"]},
    )

    assert r.status_code == 403


async def test_l_assigne_ne_glisse_pas_un_champ_interdit_avec_le_statut(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le contrôle porte sur l'ensemble des champs envoyés, pas sur le premier."""
    changement, tache, gens = await _changement_avec_tache(session, "melange")

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(gens["porteur"]),
        json={"statut": "Terminée", "echeance": "2026-12-31"},
    )

    assert r.status_code == 403, r.text


@pytest.mark.parametrize("role", ["admin", "responsable", "contributeur"])
async def test_les_acteurs_modifient_tous_les_champs(
    client: AsyncClient, session: AsyncSession, role: str
) -> None:
    changement, tache, gens = await _changement_avec_tache(session, f"acteur-{role}")

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(gens[role]),
        json={"titre": "Déployer en production", "echeance": "2026-12-31"},
    )

    assert r.status_code == 200, f"{role} : {r.text}"


async def test_poser_une_echeance_est_journalise_sans_planter(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Régression : `json.dumps` refusait les dates, et l'audit faisait tomber toute la requête."""
    changement, tache, gens = await _changement_avec_tache(session, "audit-date")

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(gens["admin"]),
        json={"echeance": "2026-12-31"},
    )

    assert r.status_code == 200, r.text
    journal = (await client.get("/admin/journal?page=1", headers=entetes(gens["admin"]))).json()
    assert any(e["action"] == "MODIFICATION" for e in journal["elements"])


async def test_un_tiers_ne_touche_a_rien(client: AsyncClient, session: AsyncSession) -> None:
    changement, tache, gens = await _changement_avec_tache(session, "tiers")

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(gens["tiers"]),
        json={"statut": "Terminée"},
    )

    assert r.status_code == 403, "il n'est ni acteur, ni assigné de cette tâche"


async def test_on_n_assigne_pas_une_tache_a_un_agent_sans_acces_au_module(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, tache, gens = await _changement_avec_tache(session, "ineligible")
    from sqlalchemy import text

    await session.execute(
        text(
            "DELETE FROM core.acces_role "
            "WHERE profil_code = 'SUPPORT_APP' AND acces = 'changements'"
        )
    )
    await session.commit()
    sans_acces = await creer_utilisateur(
        session, email="sansacces.tache@afgbank.ml", profil="SUPPORT_APP"
    )

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(gens["admin"]),
        json={"assigne_id": sans_acces},
    )

    assert r.status_code == 422, r.text


# --- Projets : mêmes règles ----------------------------------------------------------------------


async def test_l_assigne_d_une_tache_de_projet_ne_change_que_le_statut(
    client: AsyncClient, session: AsyncSession
) -> None:
    gens = {}
    for role in ("responsable", "porteur"):
        gens[role] = await creer_utilisateur(
            session, email=f"{role}.prjtache@afgbank.ml", profil="SUPPORT_APP_HELPDESK"
        )
    projet = await creer_activite(
        session, module="projet", reference="PRJ-TCH-1", responsable_id=gens["responsable"]
    )
    from sqlalchemy import text

    tache = await session.scalar(
        text(
            "INSERT INTO core.tache (activite_id, titre, statut, assigne_id) "
            "VALUES (cast(:aid as uuid), 'Rédiger le cadrage', 'À faire', cast(:uid as uuid)) "
            "RETURNING id::text"
        ),
        {"aid": projet, "uid": gens["porteur"]},
    )
    await session.commit()

    assert (
        await client.patch(
            f"/projets/{projet}/taches/{tache}",
            headers=entetes(gens["porteur"]),
            json={"statut": "En cours"},
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/projets/{projet}/taches/{tache}",
            headers=entetes(gens["porteur"]),
            json={"echeance": "2026-12-31"},
        )
    ).status_code == 403

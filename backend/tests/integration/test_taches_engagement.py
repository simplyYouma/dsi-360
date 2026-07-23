"""Ce qu'une tâche doit avoir pour avancer, et ce qu'on ne lui reprend plus une fois finie.

Deux règles, nées du même incident : des tâches passées « Terminée » en lot, sans porteur ni
date. L'avancement du projet mentait, et personne ne pouvait dire qui avait fait quoi.

1. On n'engage ni ne termine une tâche sans responsable **et** sans échéance.
2. Une tâche terminée ne se retouche plus : pour corriger, on la rouvre — ce qui laisse une trace.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def _changement(session: AsyncSession, suffixe: str) -> tuple[str, str]:
    admin = await creer_utilisateur(session, email=f"admin.{suffixe}@afgbank.ml", profil="ADMIN")
    changement = await creer_activite(
        session, module="changement", reference=f"CHG-ENG-{suffixe}", responsable_id=admin
    )
    return changement, admin


async def _tache(
    session: AsyncSession,
    activite_id: str,
    *,
    assigne_id: str | None = None,
    avec_echeance: bool = False,
    statut: str = "À faire",
) -> str:
    tache = await session.scalar(
        text(
            "INSERT INTO core.tache (activite_id, titre, statut, assigne_id, echeance) "
            "VALUES (cast(:aid as uuid), 'Déployer', :statut, cast(:uid as uuid), "
            "        CASE WHEN :ech THEN current_date + 7 ELSE NULL END) "
            "RETURNING id::text"
        ),
        {"aid": activite_id, "uid": assigne_id, "statut": statut, "ech": avec_echeance},
    )
    await session.commit()
    return str(tache)


@pytest.mark.parametrize(
    ("assigne", "echeance", "attendu"),
    [(False, False, "responsable"), (True, False, "échéance"), (False, True, "responsable")],
)
async def test_une_tache_incomplete_ne_se_termine_pas(
    client: AsyncClient, session: AsyncSession, assigne: bool, echeance: bool, attendu: str
) -> None:
    suffixe = f"inc-{int(assigne)}{int(echeance)}"
    changement, admin = await _changement(session, suffixe)
    tache = await _tache(
        session, changement, assigne_id=admin if assigne else None, avec_echeance=echeance
    )

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(admin),
        json={"statut": "Terminée"},
    )

    assert r.status_code == 409, r.text
    assert attendu in r.json()["detail"]


async def test_on_complete_et_on_termine_dans_le_meme_geste(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le contrôle juge l'état final, pas l'état de départ : tout renseigner d'un coup passe."""
    changement, admin = await _changement(session, "complet")
    tache = await _tache(session, changement)

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(admin),
        json={"statut": "Terminée", "assigne_id": admin, "echeance": "2026-12-31"},
    )

    assert r.status_code == 200, r.text


async def test_une_tache_terminee_ne_se_retouche_plus(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, admin = await _changement(session, "figee")
    tache = await _tache(
        session, changement, assigne_id=admin, avec_echeance=True, statut="Terminée"
    )

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(admin),
        json={"echeance": "2027-01-31"},
    )

    assert r.status_code == 409, r.text
    assert "rouvrez" in r.json()["detail"].lower()


async def test_rouvrir_et_corriger_dans_le_meme_geste_est_permis(
    client: AsyncClient, session: AsyncSession
) -> None:
    changement, admin = await _changement(session, "rouvre")
    tache = await _tache(
        session, changement, assigne_id=admin, avec_echeance=True, statut="Terminée"
    )

    r = await client.patch(
        f"/changements/{changement}/taches/{tache}",
        headers=entetes(admin),
        json={"statut": "En cours", "echeance": "2027-01-31"},
    )

    assert r.status_code == 200, r.text

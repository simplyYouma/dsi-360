"""On ne déclare pas abouti un dossier dont des tâches restent en plan.

Clore un projet aux tâches inachevées, c'est faire disparaître du travail des écrans de ceux qui
le portent, et laisser un avancement qui ment. La règle vaut pour l'écran (bouton grisé, motif au
survol) **et** pour le serveur — le grisage n'est pas une barrière.

Ce qu'elle ne bloque jamais : abandonner, rejeter, ou clore un dossier déjà en repli (retour
arrière) — ses tâches sont alors sans objet.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _projet_avec_tache(
    client: AsyncClient, session: AsyncSession, suffixe: str, *, terminee: bool
) -> tuple[str, str]:
    admin = await creer_utilisateur(
        session, email=f"admin.{suffixe}@afgbank.ml", profil="ADMIN"
    )
    projet = (
        await client.post(
            "/projets",
            headers=entetes(admin),
            json={"titre": f"Projet {suffixe}", "responsable_id": admin},
        )
    ).json()
    # Par l'API, pas en SQL : c'est la création d'une tâche qui fait quitter « Cadrage », et
    # l'avancement se recalcule côté serveur. Une insertion directe laisserait le projet dans un
    # état qu'aucun usage réel ne produit.
    tache = (
        await client.post(
            f"/projets/{projet['id']}/taches",
            headers=entetes(admin),
            json={
                "titre": "Reste à faire",
                "assigne_id": admin,
                "echeance": "2026-12-31",
            },
        )
    ).json()
    identifiants = (
        await client.get(f"/projets/{projet['id']}/taches", headers=entetes(admin))
    ).json()
    assert tache is not None
    if terminee:
        r = await client.patch(
            f"/projets/{projet['id']}/taches/{identifiants[0]['id']}",
            headers=entetes(admin),
            json={"statut": "Terminée"},
        )
        assert r.status_code == 200, r.text
    return projet["id"], admin


async def test_la_cloture_est_refusee_tant_qu_une_tache_traine(
    client: AsyncClient, session: AsyncSession
) -> None:
    projet, admin = await _projet_avec_tache(client, session, "cloture-bloquee", terminee=False)

    detail = (await client.get(f"/projets/{projet}", headers=entetes(admin))).json()
    assert "Clôturé" in detail["transitions_bloquees"], detail["transitions_bloquees"]
    assert "pas terminée" in detail["transitions_bloquees"]["Clôturé"]

    r = await client.post(
        f"/projets/{projet}/transition",
        headers=entetes(admin),
        json={"vers": "Clôturé", "note": "On clôt quand même"},
    )
    assert r.status_code == 409, r.text


async def test_la_cloture_passe_quand_tout_est_termine(
    client: AsyncClient, session: AsyncSession
) -> None:
    projet, admin = await _projet_avec_tache(client, session, "cloture-ok", terminee=True)

    detail = (await client.get(f"/projets/{projet}", headers=entetes(admin))).json()
    assert detail["transitions_bloquees"] == {}

    r = await client.post(
        f"/projets/{projet}/transition",
        headers=entetes(admin),
        json={"vers": "Clôturé", "note": "Livrables recettés"},
    )
    assert r.status_code == 200, r.text


async def test_une_suspension_reste_toujours_possible(
    client: AsyncClient, session: AsyncSession
) -> None:
    """La garde vise l'aboutissement, pas la sortie : sinon un projet bloqué serait enfermé."""
    projet, admin = await _projet_avec_tache(client, session, "suspendre", terminee=False)

    detail = (await client.get(f"/projets/{projet}", headers=entetes(admin))).json()
    assert "Suspendu" not in detail["transitions_bloquees"]

    r = await client.post(
        f"/projets/{projet}/transition",
        headers=entetes(admin),
        json={"vers": "Suspendu", "note": "Budget gelé"},
    )
    assert r.status_code == 200, r.text

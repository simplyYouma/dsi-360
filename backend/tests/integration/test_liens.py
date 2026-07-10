"""Les liens utiles appartiennent à l'activité, jamais à une tâche.

Un lien (espace documentaire, wiki, dossier réseau) sert le sujet, pas une étape de sa réalisation.
Éparpillés sur les tâches, ils devenaient introuvables une fois la tâche terminée.
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def test_la_colonne_de_liaison_a_une_tache_a_disparu(session: AsyncSession) -> None:
    """La capacité est retirée du modèle, pas seulement masquée à l'écran."""
    colonne = await session.scalar(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'core' AND table_name = 'lien' AND column_name = 'tache_id'"
        )
    )

    assert colonne is None


async def test_un_lien_se_pose_sur_l_activite(client: AsyncClient, session: AsyncSession) -> None:
    admin = await creer_utilisateur(session, email="admin.lien@afgbank.ml", profil="ADMIN")
    changement = await creer_activite(session, module="changement", reference="CHG-LIEN-1")

    r = await client.post(
        f"/changements/{changement}/liens",
        headers=entetes(admin),
        json={"libelle": "Runbook", "url": "https://intranet.afgbank.ml/runbook"},
    )

    assert r.status_code == 201, r.text
    liens = (await client.get(f"/changements/{changement}/liens", headers=entetes(admin))).json()
    assert [lien["libelle"] for lien in liens] == ["Runbook"]


async def test_le_parametre_tache_n_est_plus_reconnu(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un `?tache=` résiduel n'ouvre plus de sous-liste : la route l'ignore purement."""
    admin = await creer_utilisateur(session, email="admin.lien2@afgbank.ml", profil="ADMIN")
    changement = await creer_activite(session, module="changement", reference="CHG-LIEN-2")
    await client.post(
        f"/changements/{changement}/liens",
        headers=entetes(admin),
        json={"libelle": "Wiki", "url": "https://intranet.afgbank.ml/wiki"},
    )

    r = await client.get(
        f"/changements/{changement}/liens?tache=00000000-0000-0000-0000-000000000000",
        headers=entetes(admin),
    )

    assert r.status_code == 200, r.text
    assert len(r.json()) == 1, "les liens de l'activité, quel que soit le paramètre résiduel"


async def test_les_projets_exposent_aussi_leurs_liens(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.lien3@afgbank.ml", profil="ADMIN")
    projet = await creer_activite(session, module="projet", reference="PRJ-LIEN-1")

    r = await client.post(
        f"/projets/{projet}/liens",
        headers=entetes(admin),
        json={"libelle": "Dossier COPIL", "url": "https://intranet.afgbank.ml/copil"},
    )

    assert r.status_code == 201, r.text

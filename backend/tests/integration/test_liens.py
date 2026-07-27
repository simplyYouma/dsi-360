"""Les liens utiles appartiennent à l'activité, jamais à une tâche.

Un lien (espace documentaire, wiki, dossier réseau) sert le sujet, pas une étape de sa réalisation.
Éparpillés sur les tâches, ils devenaient introuvables une fois la tâche terminée.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes

# Modules dont l'écran (FicheTransition avecLiens / PageActiviteCategorie) propose l'ajout de
# liens : chacun DOIT exposer la route côté serveur, sinon l'utilisateur voit une erreur en prod.
# (base d'URL, module de l'activité). Gouvernance/cybersécurité/audit ont longtemps manqué.
MODULES_AVEC_LIENS = [
    ("changements", "changement"),
    ("projets", "projet"),
    ("risques", "risque"),
    ("audit", "audit"),
    ("cybersecurite", "cybersecurite"),
    ("gouvernance", "gouvernance"),
]


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


@pytest.mark.parametrize(("base", "module"), MODULES_AVEC_LIENS)
async def test_chaque_module_a_liens_recoit_et_rend_ses_liens(
    client: AsyncClient, session: AsyncSession, base: str, module: str
) -> None:
    """Là où l'écran propose l'ajout, le serveur doit le recevoir (POST) et le restituer (GET).

    Le POST échouait en 405 pour gouvernance, cybersécurité et audit : la route n'était câblée
    que pour les modules à tâches. L'utilisateur voyait alors une erreur en prod.
    """
    admin = await creer_utilisateur(
        session, email=f"admin.lien.{module}@afgbank.ml", profil="ADMIN"
    )
    ident = await creer_activite(session, module=module, reference=f"LIEN-{module.upper()}-1")

    ajout = await client.post(
        f"/{base}/{ident}/liens",
        headers=entetes(admin),
        json={"libelle": "Dossier de référence", "url": "https://intranet.afgbank.ml/ref"},
    )
    assert ajout.status_code == 201, ajout.text

    liste = await client.get(f"/{base}/{ident}/liens", headers=entetes(admin))
    assert liste.status_code == 200, liste.text
    assert [lien["libelle"] for lien in liste.json()] == ["Dossier de référence"]


@pytest.mark.parametrize(
    ("base", "module"), [("gouvernance", "gouvernance"), ("risques", "risque")]
)
async def test_l_ajout_d_un_lien_apparait_dans_l_historique(
    client: AsyncClient, session: AsyncSession, base: str, module: str
) -> None:
    """Ajouter un lien laisse une trace lisible dans le journal de la fiche — pas seulement en base.

    Le journal filtrait sur ``cible_type = module`` et excluait donc les liens (cible_type 'lien').
    """
    admin = await creer_utilisateur(
        session, email=f"admin.histo.{module}@afgbank.ml", profil="ADMIN"
    )
    ident = await creer_activite(session, module=module, reference=f"HISTO-{module.upper()}-1")

    await client.post(
        f"/{base}/{ident}/liens",
        headers=entetes(admin),
        json={"libelle": "Espace COPIL", "url": "https://intranet.afgbank.ml/copil"},
    )

    detail = (await client.get(f"/{base}/{ident}", headers=entetes(admin))).json()
    lignes = [e for e in detail["journal"] if e["action"] == "LIEN_AJOUTE"]
    assert len(lignes) == 1, "l'ajout du lien doit figurer au journal de la fiche"
    assert "Espace COPIL" in (lignes[0]["detail"] or "")

"""Un dossier terminé ne court plus après son délai.

Cas signalé : une action de gouvernance au statut « Réalisé », rangée dans « Terminés », affichait
pourtant « Dépassé · 40 j » dans la colonne SLA — et gonflait la carte « En retard » du tableau de
bord. En cause : le gel du compteur reposait sur `resolu_le` / `cloture_le`, or seuls « Résolu » et
« Clôturé » les posent. « Réalisé », « Rejeté », « Maîtrisé » n'en posent aucun.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def _echeance_depassee(session: AsyncSession, ident: str, statut: str) -> None:
    """Le dossier porte un statut terminal SANS horodatage, et une échéance largement passée."""
    await session.execute(
        text(
            "UPDATE core.activite SET statut = :s, "
            "sla_resolution_le = now() - interval '40 days', "
            "resolu_le = NULL, cloture_le = NULL WHERE id = cast(:i as uuid)"
        ),
        {"s": statut, "i": ident},
    )
    await session.commit()


# Les modules qui affichent une colonne SLA. Risques et projets n'en ont pas : leur liste montre
# la criticité et l'avancement, pas un délai.
@pytest.mark.parametrize(
    ("module", "chemin", "statut"),
    [
        ("gouvernance", "/gouvernance", "Réalisé"),
        ("changement", "/changements", "Rejeté"),
        ("cybersecurite", "/cybersecurite", "Corrigé"),
    ],
)
async def test_le_sla_d_un_dossier_termine_ne_court_plus(
    client: AsyncClient, session: AsyncSession, module: str, chemin: str, statut: str
) -> None:
    admin = await creer_utilisateur(
        session, email=f"admin.sla{len(statut)}@afgbank.ml", profil="ADMIN"
    )
    ident = await creer_activite(session, module=module, reference=f"REF-SLA-{statut}")
    await _echeance_depassee(session, ident, statut)

    r = await client.get(f"{chemin}?etat=tous", headers=entetes(admin))

    assert r.status_code == 200, r.text
    ligne = next(e for e in r.json()["elements"] if e["reference"] == f"REF-SLA-{statut}")
    assert ligne["statut_sla"] == "termine", "ni « dépassé », ni « à l'heure » : c'est fini"
    assert ligne["sla_arrete"] is True


async def test_un_dossier_en_cours_reste_bien_depasse(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le garde-fou : on ne vient pas d'éteindre l'alerte pour tout le monde."""
    admin = await creer_utilisateur(session, email="admin.sla.vivant@afgbank.ml", profil="ADMIN")
    ident = await creer_activite(session, module="gouvernance", reference="REF-SLA-VIVANT")
    await _echeance_depassee(session, ident, "En cours")

    r = await client.get("/gouvernance?etat=tous", headers=entetes(admin))

    ligne = next(e for e in r.json()["elements"] if e["reference"] == "REF-SLA-VIVANT")
    assert ligne["statut_sla"] == "depasse"
    assert ligne["sla_arrete"] is False


async def test_la_carte_en_retard_ignore_les_dossiers_termines(
    client: AsyncClient, session: AsyncSession
) -> None:
    """« En retard » compte ce qu'il reste à traiter — pas ce qui est déjà réglé."""
    admin = await creer_utilisateur(session, email="admin.sla.carte@afgbank.ml", profil="ADMIN")
    avant = (await client.get("/tableau-de-bord", headers=entetes(admin))).json()["cartes"][
        "en_retard"
    ]

    fini = await creer_activite(session, module="gouvernance", reference="REF-CARTE-FINI")
    await _echeance_depassee(session, fini, "Réalisé")
    apres_fini = (await client.get("/tableau-de-bord", headers=entetes(admin))).json()["cartes"][
        "en_retard"
    ]
    assert apres_fini == avant, "une action réalisée ne gonfle pas le compteur"

    vivant = await creer_activite(session, module="gouvernance", reference="REF-CARTE-VIVANT")
    await _echeance_depassee(session, vivant, "En cours")
    apres_vivant = (await client.get("/tableau-de-bord", headers=entetes(admin))).json()["cartes"][
        "en_retard"
    ]
    assert apres_vivant == avant + 1, "une action en cours et dépassée, si"


async def test_le_filtre_en_retard_ignore_aussi_les_termines(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Même règle dans la liste : le filtre « En retard » ne montre que du travail à faire."""
    admin = await creer_utilisateur(session, email="admin.sla.filtre@afgbank.ml", profil="ADMIN")
    fini = await creer_activite(session, module="gouvernance", reference="REF-FILTRE-FINI")
    vivant = await creer_activite(session, module="gouvernance", reference="REF-FILTRE-VIVANT")
    await _echeance_depassee(session, fini, "Réalisé")
    await _echeance_depassee(session, vivant, "En cours")

    r = await client.get("/gouvernance?retard=true", headers=entetes(admin))

    refs = {e["reference"] for e in r.json()["elements"]}
    assert "REF-FILTRE-VIVANT" in refs
    assert "REF-FILTRE-FINI" not in refs


async def test_le_compteur_en_retard_de_la_liste_suit_la_meme_regle(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="admin.sla.stats@afgbank.ml", profil="ADMIN")
    avant = (await client.get("/gouvernance/stats", headers=entetes(admin))).json()["en_retard"]

    fini = await creer_activite(session, module="gouvernance", reference="REF-STATS-FINI")
    await _echeance_depassee(session, fini, "Réalisé")

    apres = (await client.get("/gouvernance/stats", headers=entetes(admin))).json()["en_retard"]
    assert apres == avant

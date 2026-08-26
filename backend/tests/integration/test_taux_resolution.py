"""Taux de résolution : ce qui a abouti sur ce qui est arrivé.

Le piège de cet indicateur est sa définition. Un dossier « Rejeté » ou « Annulé » est arrêté, pas
résolu : le compter comme une résolution flatterait le chiffre exactement là où il doit alerter.
On vérifie donc la définition, pas seulement la présence du champ.
"""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, entetes


async def _statut(session: AsyncSession, reference: str, statut: str) -> None:
    await session.execute(
        text("UPDATE core.activite SET statut = :s WHERE reference = :r"),
        {"s": statut, "r": reference},
    )
    await session.commit()


def _module(analyses: dict, module: str) -> dict:
    ligne = next((r for r in analyses["resolution_par_module"] if r["module"] == module), None)
    assert ligne is not None, analyses["resolution_par_module"]
    return ligne


async def test_le_taux_compte_les_dossiers_aboutis(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="res.base@afgbank.ml", profil="ADMIN")
    for i in range(4):
        await creer_activite(
            session, module="incident", reference=f"INC-2026-88{i:03d}", responsable_id=admin
        )
    await _statut(session, "INC-2026-88000", "Résolu")
    await _statut(session, "INC-2026-88001", "Clôturé")

    a = (await client.get("/analyses?modules=incident", headers=entetes(admin))).json()
    ligne = _module(a, "incident")
    assert ligne["recus"] == 4
    assert ligne["resolus"] == 2
    assert ligne["en_cours"] == 2
    assert ligne["taux"] == 50


async def test_un_dossier_rejete_n_est_pas_une_resolution(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Il est arrêté, pas résolu : hors du numérateur, mais bien au dénominateur."""
    admin = await creer_utilisateur(session, email="res.rejet@afgbank.ml", profil="ADMIN")
    await creer_activite(
        session, module="demande", reference="DEM-2026-88100", responsable_id=admin
    )
    await creer_activite(
        session, module="demande", reference="DEM-2026-88101", responsable_id=admin
    )
    await _statut(session, "DEM-2026-88100", "Clôturée")
    await _statut(session, "DEM-2026-88101", "Rejetée")

    a = (await client.get("/analyses?modules=demande", headers=entetes(admin))).json()
    ligne = _module(a, "demande")
    assert ligne["recus"] == 2
    assert ligne["resolus"] == 1
    assert ligne["abandonnes"] == 1
    assert ligne["en_cours"] == 0
    # Un dossier abandonné pèse au dénominateur : le taux ne peut pas être de 100 %.
    assert ligne["taux"] == 50


async def test_le_kpi_global_recoupe_le_detail_par_module(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await creer_utilisateur(session, email="res.kpi@afgbank.ml", profil="ADMIN")
    await creer_activite(
        session, module="incident", reference="INC-2026-88200", responsable_id=admin
    )
    await _statut(session, "INC-2026-88200", "Résolu")

    a = (await client.get("/analyses", headers=entetes(admin))).json()
    recus = sum(r["recus"] for r in a["resolution_par_module"])
    resolus = sum(r["resolus"] for r in a["resolution_par_module"])
    attendu = round(resolus * 100 / recus) if recus else 0
    assert a["kpis"]["taux_resolution"] == attendu


async def test_le_filtre_par_module_s_applique_au_taux(
    client: AsyncClient, session: AsyncSession
) -> None:
    """« Si on a le tout, on filtre » : le taux suit le périmètre regardé."""
    admin = await creer_utilisateur(session, email="res.filtre@afgbank.ml", profil="ADMIN")
    await creer_activite(
        session, module="incident", reference="INC-2026-88300", responsable_id=admin
    )
    await creer_activite(
        session, module="projet", reference="PRJ-2026-88300", responsable_id=admin
    )
    await _statut(session, "INC-2026-88300", "Résolu")

    filtre = (await client.get("/analyses?modules=incident", headers=entetes(admin))).json()
    assert {r["module"] for r in filtre["resolution_par_module"]} == {"incident"}

    tous = (await client.get("/analyses", headers=entetes(admin))).json()
    assert {r["module"] for r in tous["resolution_par_module"]} >= {"incident", "projet"}

"""Répartition mensuelle : volumétrie par priorité + SLA, et DSI vs DBS, par mois."""

import json
from datetime import datetime

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_utilisateur, entetes


async def _incident_importe(
    session: AsyncSession,
    *,
    reference: str,
    cree_le: str,
    priorite: int,
    ttr_minutes: int,
    responsable_id: str | None,
    ferme: bool,
    gestionnaire: str | None = None,
) -> None:
    quand = datetime.fromisoformat(cree_le)
    donnees: dict[str, object] = {"ttr_minutes": ttr_minutes}
    # Le nom porté par le fichier : c'est lui qui range le ticket chez DBS (ADR-0005).
    if gestionnaire is not None:
        donnees["gestionnaire"] = gestionnaire
    await session.execute(
        text(
            "INSERT INTO core.activite "
            "(reference, module, titre, statut, priorite, impact, urgence, responsable_id, "
            " source, source_id, cree_le, cloture_le, donnees) "
            "VALUES (:ref, 'incident', 'Ticket importé', :statut, :prio, 3, 3, "
            " cast(:resp as uuid), 'IMPORT_SD', :ref, :cree, :cloture, cast(:d as jsonb))"
        ),
        {
            "ref": reference,
            "statut": "Clôturé" if ferme else "Ouvert",
            "prio": priorite,
            "resp": responsable_id,
            "cree": quand,
            "cloture": quand if ferme else None,
            "d": json.dumps(donnees),
        },
    )
    await session.commit()


async def test_repartition_mensuelle(client: AsyncClient, session: AsyncSession) -> None:
    admin = await creer_utilisateur(session, email="admin.mens@afgbank.ml", profil="ADMIN")
    gestionnaire = await creer_utilisateur(session, email="gest.mens@afgbank.ml")

    # Mars 2023 : deux P1. Un géré DSI, résolu dans les temps ; un DBS, hors délai.
    await _incident_importe(
        session, reference="IMP-M1", cree_le="2023-03-15", priorite=1,
        ttr_minutes=120, responsable_id=gestionnaire, ferme=True,
    )
    await _incident_importe(
        session, reference="IMP-M2", cree_le="2023-03-20", priorite=1,
        ttr_minutes=6000, responsable_id=None, ferme=True, gestionnaire="Agent DBS",
    )

    # Étendue > 3 mois → granularité mensuelle ; les deux tickets tombent dans le bucket « mars ».
    r = await client.get(
        "/analyses/mensuel?du=2023-01-01&au=2023-06-30", headers=entetes(admin)
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["granularite"] == "mois"
    # La fenêtre réellement agrégée est annoncée : sans elle, on rapproche ces totaux de ceux
    # d'une liste sans savoir qu'ils ne portent pas sur la même période.
    assert data["debut"].startswith("2023-01"), data["debut"]
    assert data["fin"] > data["debut"]
    cles = [m["cle"] for m in data["mois"]]
    assert "2023-03" in cles
    i = cles.index("2023-03")
    assert data["mois"][i]["libelle"] == "mars 23"

    p1 = next(p for p in data["priorites"] if p["priorite"] == 1)
    cell = p1["cellules"][i]
    assert cell["total"] == 2
    assert cell["population_sla"] == 2
    assert cell["sla_taux"] == 50.0  # 1 des 2 dans les temps

    total = data["total_priorites"][i]
    assert total["total"] == 2
    assert total["sla_taux"] == 50.0

    par_entite = {e["cle"]: e for e in data["entites"]}
    assert par_entite["DSI"]["cellules"][i]["total"] == 1
    assert par_entite["DBS"]["cellules"][i]["total"] == 1
    assert par_entite["DSI"]["total"] == 1
    assert par_entite["DBS"]["incidents"] == 1


async def test_granularite_suit_le_filtre(client: AsyncClient, session: AsyncSession) -> None:
    admin = await creer_utilisateur(session, email="admin.gran@afgbank.ml", profil="ADMIN")
    # Une semaine → granularité journalière (un bucket par jour).
    r = await client.get("/analyses/mensuel?du=2023-03-01&au=2023-03-07", headers=entetes(admin))
    assert r.json()["granularite"] == "jour"
    # Deux ans et demi → granularité annuelle.
    r = await client.get("/analyses/mensuel?du=2021-01-01&au=2023-06-30", headers=entetes(admin))
    assert r.json()["granularite"] == "annee"

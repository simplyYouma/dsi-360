"""Analyses de flux et de qualité : durées par statut, réouvertures, vieillissement, DBS, Pareto.

Chaque agrégat se vérifie sur des données posées à la main : si la requête dérive, le chiffre
raconté à la Direction dérive avec elle.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import creer_activite, creer_utilisateur, designer, entetes


async def _admin(session: AsyncSession, email: str) -> str:
    return await creer_utilisateur(session, email=email, profil="ADMIN")


async def _journal(
    session: AsyncSession,
    module: str,
    reference: str,
    etats: list[tuple[str, datetime]],
) -> None:
    """Trace un parcours dans le journal (empreintes factices : on teste l'agrégation)."""
    precedent = None
    for i, (statut, quand) in enumerate(etats):
        await session.execute(
            text(
                "INSERT INTO audit.journal (horodatage, acteur_email, module, action, "
                " cible_type, cible_id, nouvelle_valeur, hash_precedent, hash_courant) "
                "VALUES (:h, 'test@afgbank.ml', :m, :a, :m, :r, "
                " cast(:nv as jsonb), :hp, :hc)"
            ),
            {
                "h": quand,
                "m": module,
                "a": "CREATION" if i == 0 else "TRANSITION",
                "r": reference,
                "nv": f'{{"statut": "{statut}"}}',
                "hp": precedent,
                "hc": f"test-{reference}-{i}",
            },
        )
        precedent = f"test-{reference}-{i}"


async def _analyses(client: AsyncClient, admin: str) -> dict[str, Any]:
    r = await client.get("/analyses", headers=entetes(admin))
    assert r.status_code == 200, r.text
    return dict(r.json())


async def test_duree_par_statut_mesure_les_sejours_termines(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Deux jours en « Ouvert » : la moyenne doit dire 2, et ignorer le séjour en cours."""
    admin = await _admin(session, "admin.flux1@afgbank.ml")
    await creer_activite(session, module="incident", reference="INC-FLX-1")
    t0 = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    await _journal(
        session,
        "incident",
        "INC-FLX-1",
        [("Ouvert", t0), ("Résolu", t0 + timedelta(days=2))],
    )

    durees = (await _analyses(client, admin))["durees_statuts"]

    ouvert = next(d for d in durees if d["module"] == "incident" and d["statut"] == "Ouvert")
    assert ouvert["jours"] == 2.0
    assert ouvert["passages"] == 1
    # « Résolu » est un séjour encore ouvert : il ne doit pas apparaître.
    assert not any(d["statut"] == "Résolu" and d["module"] == "incident" for d in durees)


async def test_les_reouvertures_se_comptent_depuis_le_journal(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le statut courant oublie un ticket rouvert puis résolu : le journal, non."""
    admin = await _admin(session, "admin.flux2@afgbank.ml")
    await creer_activite(session, module="incident", reference="INC-FLX-2", statut="Résolu")
    await session.execute(
        text("UPDATE core.activite SET resolu_le = now() WHERE reference = 'INC-FLX-2'")
    )
    t0 = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    await _journal(
        session,
        "incident",
        "INC-FLX-2",
        [
            ("Ouvert", t0),
            ("Résolu", t0 + timedelta(days=1)),
            ("Réouvert", t0 + timedelta(days=2)),
            ("Résolu", t0 + timedelta(days=3)),
        ],
    )

    reouvertures = (await _analyses(client, admin))["reouvertures"]

    incident = next(r for r in reouvertures if r["libelle"] == "incident")
    assert incident["rouverts"] == 1
    assert incident["resolus"] >= 1


async def test_le_vieillissement_range_le_stock_ouvert(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _admin(session, "admin.flux3@afgbank.ml")
    recent = await creer_activite(session, module="changement", reference="CHG-FLX-3")
    ancien = await creer_activite(session, module="changement", reference="CHG-FLX-3B")
    maj = (
        "UPDATE core.activite SET cree_le = now() - make_interval(days => :j) "
        "WHERE id = cast(:a as uuid)"
    )
    await session.execute(text(maj), {"j": 2, "a": recent})
    await session.execute(text(maj), {"j": 45, "a": ancien})

    vieillissement = (await _analyses(client, admin))["vieillissement"]

    tranches = {v["libelle"]: v["valeur"] for v in vieillissement}
    assert set(tranches) == {"≤ 7 j", "8–30 j", "31–90 j", "> 90 j"}
    assert tranches["≤ 7 j"] >= 1
    assert tranches["31–90 j"] >= 1


async def test_la_part_dbs_se_mesure(client: AsyncClient, session: AsyncSession) -> None:
    """Un ticket importé sans responsable est chez DBS : il doit compter, avec son âge."""
    admin = await _admin(session, "admin.flux4@afgbank.ml")
    agent = await creer_utilisateur(session, email="agent.flux4@afgbank.ml")
    await creer_activite(session, module="incident", reference="INC-FLX-4", responsable_id=agent)
    chez_dbs = await creer_activite(session, module="incident", reference="INC-FLX-4B")
    await session.execute(
        text(
            "UPDATE core.activite SET source = 'IMPORT_SD', "
            "cree_le = now() - interval '10 days' WHERE reference IN ('INC-FLX-4', 'INC-FLX-4B')"
        )
    )
    assert chez_dbs  # responsable_id absent -> DBS

    dbs = (await _analyses(client, admin))["dbs"]

    assert dbs["dsi"] >= 1
    assert dbs["dbs"] >= 1
    assert dbs["dbs_ouverts"] >= 1
    assert dbs["dbs_age_jours"] is not None and dbs["dbs_age_jours"] >= 9


async def test_le_pareto_des_categories_cumule(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _admin(session, "admin.flux5@afgbank.ml")
    await session.execute(
        text(
            "INSERT INTO core.categorie (module, code, libelle) VALUES "
            "('incident', 'FLX-RESEAU', 'Réseau (flux)'), ('incident', 'FLX-POSTE', 'Poste (flux)')"
        )
    )
    for i, code in enumerate(["FLX-RESEAU", "FLX-RESEAU", "FLX-RESEAU", "FLX-POSTE"]):
        ident = await creer_activite(session, module="incident", reference=f"INC-FLX-5{i}")
        await session.execute(
            text(
                "UPDATE core.activite SET categorie_id = "
                "(SELECT id FROM core.categorie WHERE code = :c) WHERE id = cast(:a as uuid)"
            ),
            {"c": code, "a": ident},
        )

    pareto = (await _analyses(client, admin))["pareto_categories"]

    assert pareto, "au moins une catégorie attendue"
    assert pareto[0]["valeur"] >= pareto[-1]["valeur"], "trié par volume décroissant"
    assert pareto[-1]["cumul_pct"] <= 100
    assert all(
        a["cumul_pct"] <= b["cumul_pct"] for a, b in zip(pareto, pareto[1:], strict=False)
    ), "le cumul ne redescend jamais"


async def test_la_prise_en_charge_se_compare_a_sa_cible(
    client: AsyncClient, session: AsyncSession
) -> None:
    """P1 : 15 minutes pour prendre en charge. 10 min = tenu, 60 min = manqué."""
    admin = await _admin(session, "admin.flux6@afgbank.ml")
    for ref, trep in (("INC-FLX-6", 10), ("INC-FLX-6B", 60)):
        ident = await creer_activite(session, module="incident", reference=ref)
        await session.execute(
            text(
                "UPDATE core.activite SET source = 'IMPORT_SD', priorite = 1, "
                "donnees = donnees || cast(:d as jsonb) WHERE id = cast(:a as uuid)"
            ),
            {"d": f'{{"ttrespond_minutes": {trep}}}', "a": ident},
        )

    pec = (await _analyses(client, admin))["pec_par_priorite"]

    p1 = next(x for x in pec if x["priorite"] == "P1")
    assert p1["total"] == 2
    assert p1["dans_delai"] == 1
    assert p1["taux"] == 50


async def test_les_suivis_entrent_dans_l_evaluation(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Un agent qui ne gère rien mais suit deux tickets doit apparaître, avec ses suivis."""
    admin = await _admin(session, "admin.flux7@afgbank.ml")
    suiveur = await creer_utilisateur(session, email="suiveur.flux7@afgbank.ml")
    for ref in ("INC-FLX-7", "INC-FLX-7B"):
        ident = await creer_activite(session, module="incident", reference=ref)
        await designer(session, activite_id=ident, utilisateur_id=suiveur, role="CONTRIBUTEUR")

    r = await client.get("/analyses/gestionnaires", headers=entetes(admin))
    assert r.status_code == 200, r.text

    ligne = next(e for e in r.json() if e["id"] == suiveur)
    assert ligne["suivis"] == 2
    assert ligne["volume"] == 0, "suivre n'est pas résoudre"

    detail = await client.get(f"/analyses/gestionnaire/{suiveur}", headers=entetes(admin))
    assert detail.status_code == 200, detail.text
    assert detail.json()["suivis"] == 2


async def test_risques_critiques_ne_compte_que_les_critiques(
    client: AsyncClient, session: AsyncSession
) -> None:
    """La carte du tableau de bord disait « critiques » et comptait tout le stock ouvert."""
    admin = await _admin(session, "admin.flux8@afgbank.ml")
    benin = await creer_activite(session, module="risque", reference="RSQ-FLX-8")
    critique = await creer_activite(session, module="risque", reference="RSQ-FLX-8B")
    await session.execute(
        text("UPDATE core.activite SET donnees = cast(:d as jsonb) WHERE id = cast(:a as uuid)"),
        {"d": '{"probabilite": 1, "impact": 2, "criticite": 2}', "a": benin},
    )
    await session.execute(
        text("UPDATE core.activite SET donnees = cast(:d as jsonb) WHERE id = cast(:a as uuid)"),
        {"d": '{"probabilite": 5, "impact": 4, "criticite": 5}', "a": critique},
    )

    r = await client.get("/tableau-de-bord", headers=entetes(admin))
    assert r.status_code == 200, r.text
    cartes = r.json()["cartes"]

    assert cartes["risques_critiques"] == 1
    assert cartes["risques_ouverts"] == 2


async def test_a_traiter_met_le_plus_urgent_en_tete(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Le tableau de bord doit mener aux dossiers, pas seulement les compter."""
    admin = await _admin(session, "admin.flux9@afgbank.ml")
    tard = await creer_activite(session, module="changement", reference="CHG-FLX-9")
    tot = await creer_activite(session, module="changement", reference="CHG-FLX-9B")
    maj = (
        "UPDATE core.activite SET sla_resolution_le = now() + make_interval(hours => :h) "
        "WHERE id = cast(:a as uuid)"
    )
    await session.execute(text(maj), {"h": 48, "a": tard})
    await session.execute(text(maj), {"h": -2, "a": tot})  # déjà dépassée

    r = await client.get("/tableau-de-bord", headers=entetes(admin))
    assert r.status_code == 200, r.text
    a_traiter = r.json()["a_traiter"]

    assert a_traiter, "au moins une activité attendue"
    assert a_traiter[0]["reference"] == "CHG-FLX-9B", "la plus dépassée d'abord"
    assert {"module", "id", "reference", "titre", "statut"} <= set(a_traiter[0])

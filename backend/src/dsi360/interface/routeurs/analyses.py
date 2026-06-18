"""Analyse / Reporting (cahier §8) : agrégations transverses (cloisonnées par direction).

Vise un vrai tableau analytique : KPI de pilotage (respect SLA, délai moyen de résolution,
retards), répartitions (module, priorité, direction, charge), matrice des risques
(probabilité × impact) et tendance hebdomadaire création vs résolution.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import AnalysesReponse, GestionnaireEval
from dsi360.interface.securite import exiger_acces

routeur = APIRouter(prefix="/analyses", tags=["analyses"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces("analyses"))]

_JOINTURE = "FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id"
_OUVERTES = f"{_JOINTURE} WHERE a.cloture_le IS NULL"

# Cible de résolution (minutes) par priorité — ITIL, paramétrable à terme.
_CIBLE = (
    "(CASE a.priorite WHEN 1 THEN 240 WHEN 2 THEN 480 WHEN 3 THEN 1440 "
    "WHEN 4 THEN 4320 ELSE 7200 END)"
)
_TTR = "nullif(a.donnees->>'ttr_minutes', '')::numeric"
# Population SLA réelle : tickets importés effectivement résolus (durée mesurée > 0).
_RESOLUS = f"{_JOINTURE} WHERE a.source = 'IMPORT_SD' AND a.priorite IS NOT NULL AND {_TTR} > 0"


async def _lignes(
    session: AsyncSession, requete: str, params: dict[str, Any]
) -> list[dict[str, Any]]:
    resultat = await session.execute(text(requete), params)
    return [dict(x) for x in resultat.mappings().all()]


@routeur.get("", response_model=AnalysesReponse)
async def analyses(
    courant: Courant,
    session: Session,
    jours: Annotated[int | None, Query(ge=1, le=3650)] = None,
) -> dict[str, Any]:
    cond_dir = ""
    params: dict[str, Any] = {}
    if not courant["transverse"]:
        cond_dir = " AND d.code = :dir"
        params["dir"] = courant["direction"]
    # Filtre période (sur la date de création) appliqué aux agrégations, hors tendance.
    periode = ""
    if jours is not None:
        periode = " AND a.cree_le >= now() - make_interval(days => :jours)"
        params["jours"] = jours
    cond = cond_dir + periode

    total = await session.scalar(text(f"SELECT count(*) {_OUVERTES}{cond}"), params) or 0

    par_module = await _lignes(
        session,
        f"SELECT a.module AS libelle, count(*) AS valeur {_OUVERTES}{cond} "
        "GROUP BY a.module ORDER BY valeur DESC",
        params,
    )

    par_direction = await _lignes(
        session,
        f"SELECT coalesce(d.libelle, 'Non rattachée') AS libelle, count(*) AS valeur "
        f"{_OUVERTES}{cond} GROUP BY d.libelle ORDER BY valeur DESC",
        params,
    )

    par_responsable = await _lignes(
        session,
        f"SELECT (r.prenom || ' ' || r.nom) AS libelle, count(*) AS valeur "
        f"{_JOINTURE} JOIN core.utilisateur r ON r.id = a.responsable_id "
        f"WHERE a.cloture_le IS NULL{cond} "
        "GROUP BY r.id, r.prenom, r.nom ORDER BY valeur DESC LIMIT 8",
        params,
    )

    priorites = await _lignes(
        session,
        f"SELECT a.priorite AS niveau, count(*) AS valeur {_OUVERTES} "
        f"AND a.priorite IS NOT NULL{cond} GROUP BY a.priorite ORDER BY a.priorite",
        params,
    )
    par_priorite = [{"libelle": f"P{p['niveau']}", "valeur": p["valeur"]} for p in priorites]

    sla = (
        await session.execute(
            text(
                "SELECT count(*) FILTER "
                "(WHERE a.sla_resolution_le > now() + interval '2 hours') AS a_lheure, "
                "count(*) FILTER (WHERE a.sla_resolution_le <= now() + interval '2 hours' "
                "  AND a.sla_resolution_le >= now()) AS approche, "
                "count(*) FILTER (WHERE a.sla_resolution_le < now()) AS depasse "
                f"{_OUVERTES} AND a.sla_resolution_le IS NOT NULL{cond}"
            ),
            params,
        )
    ).mappings().one()

    sla_par_module = await _lignes(
        session,
        "SELECT a.module, count(*) FILTER "
        "(WHERE a.sla_resolution_le > now() + interval '2 hours') AS a_lheure, "
        "count(*) FILTER (WHERE a.sla_resolution_le <= now() + interval '2 hours' "
        "  AND a.sla_resolution_le >= now()) AS approche, "
        "count(*) FILTER (WHERE a.sla_resolution_le < now()) AS depasse "
        f"{_OUVERTES} AND a.sla_resolution_le IS NOT NULL{cond} "
        "GROUP BY a.module ORDER BY a.module",
        params,
    )

    matrice_risques = await _lignes(
        session,
        "SELECT (a.donnees->>'probabilite')::int AS probabilite, "
        "(a.donnees->>'impact')::int AS impact, count(*) AS valeur "
        f"{_OUVERTES} AND a.module = 'risque' "
        "AND a.donnees ? 'probabilite' AND a.donnees ? 'impact'"
        f"{cond} GROUP BY (a.donnees->>'probabilite')::int, (a.donnees->>'impact')::int",
        params,
    )

    # MTTR : délai moyen de résolution (jours) sur les 90 derniers jours.
    mttr = await session.scalar(
        text(
            "SELECT round(avg(extract(epoch FROM (a.resolu_le - a.cree_le)) / 86400)::numeric, 1) "
            f"{_JOINTURE} WHERE a.resolu_le IS NOT NULL "
            f"AND a.resolu_le >= now() - interval '90 days'{cond}"
        ),
        params,
    )

    tendance = await _lignes(
        session,
        "WITH semaines AS ("
        "  SELECT generate_series(date_trunc('week', now()) - interval '7 weeks', "
        "    date_trunc('week', now()), interval '1 week') AS debut) "
        "SELECT to_char(s.debut, 'DD/MM') AS periode, "
        f"  (SELECT count(*) {_JOINTURE} WHERE a.cree_le >= s.debut "
        f"    AND a.cree_le < s.debut + interval '1 week'{cond_dir}) AS crees, "
        f"  (SELECT count(*) {_JOINTURE} WHERE a.resolu_le >= s.debut "
        f"    AND a.resolu_le < s.debut + interval '1 week'{cond_dir}) AS resolus "
        "FROM semaines s ORDER BY s.debut",
        params,
    )

    # SLA réel : respect = durée de résolution <= cible de la priorité (données importées).
    sla_prio = await _lignes(
        session,
        f"SELECT a.priorite AS niveau, count(*) AS total, "
        f"count(*) FILTER (WHERE {_TTR} <= {_CIBLE}) AS dans_delai "
        f"{_RESOLUS}{cond} GROUP BY a.priorite ORDER BY a.priorite",
        params,
    )
    sla_par_priorite = [
        {
            "priorite": f"P{p['niveau']}",
            "dans_delai": p["dans_delai"],
            "total": p["total"],
            "taux": round(p["dans_delai"] * 100 / p["total"]) if p["total"] else 0,
        }
        for p in sla_prio
    ]
    reel_total = sum(p["total"] for p in sla_par_priorite)
    reel_ok = sum(p["dans_delai"] for p in sla_par_priorite)

    # Carte d'activité : volume de tickets par jour de semaine (1=lundi) × heure.
    activite = await _lignes(
        session,
        "SELECT extract(isodow from a.cree_le)::int AS jour, "
        "extract(hour from a.cree_le)::int AS heure, count(*) AS valeur "
        f"{_JOINTURE} WHERE a.cree_le IS NOT NULL{cond} GROUP BY 1, 2",
        params,
    )

    avec_sla = sla["a_lheure"] + sla["approche"] + sla["depasse"]
    # Respect réel prioritaire (durées mesurées) ; repli sur les échéances en cours sinon.
    if reel_total > 0:
        respect = round(reel_ok * 100 / reel_total)
    elif avec_sla > 0:
        respect = round(sla["a_lheure"] * 100 / avec_sla)
    else:
        respect = 100

    return {
        "total": total,
        "kpis": {
            "ouvertes": total,
            "respect_sla": respect,
            "mttr_jours": float(mttr) if mttr is not None else 0.0,
            "en_retard": sla["depasse"],
        },
        "par_module": par_module,
        "par_direction": par_direction,
        "par_responsable": par_responsable,
        "par_priorite": par_priorite,
        "sla": {
            "a_lheure": sla["a_lheure"],
            "approche": sla["approche"],
            "depasse": sla["depasse"],
        },
        "sla_par_module": sla_par_module,
        "sla_par_priorite": sla_par_priorite,
        "matrice_risques": matrice_risques,
        "tendance": tendance,
        "activite": activite,
    }


_EVAL = text(
    "SELECT g AS gestionnaire, count(*) AS volume, "
    "count(*) FILTER (WHERE resolu_le IS NOT NULL OR cloture_le IS NOT NULL) AS resolus, "
    "round(avg(ttr) FILTER (WHERE ttr > 0) / 1440.0, 1) AS mttr_jours, "
    "round(avg(trep) FILTER (WHERE trep > 0) / 60.0, 1) AS prise_en_charge_h "
    "FROM ("
    "  SELECT a.donnees->>'gestionnaire' AS g, a.resolu_le, a.cloture_le, "
    "    nullif(a.donnees->>'ttr_minutes', '')::numeric AS ttr, "
    "    nullif(a.donnees->>'ttrespond_minutes', '')::numeric AS trep "
    "  FROM core.activite a "
    "  WHERE a.source = 'IMPORT_SD' AND coalesce(a.donnees->>'gestionnaire', '') <> ''"
    ") s GROUP BY g ORDER BY volume DESC LIMIT 15"
)


@routeur.get("/gestionnaires", response_model=list[GestionnaireEval])
async def evaluation_gestionnaires(courant: Courant, session: Session) -> list[dict[str, Any]]:
    lignes = (await session.execute(_EVAL)).mappings().all()
    return [
        {
            "gestionnaire": r["gestionnaire"],
            "volume": r["volume"],
            "resolus": r["resolus"],
            "mttr_jours": float(r["mttr_jours"]) if r["mttr_jours"] is not None else None,
            "prise_en_charge_h": float(r["prise_en_charge_h"])
            if r["prise_en_charge_h"] is not None
            else None,
        }
        for r in lignes
    ]

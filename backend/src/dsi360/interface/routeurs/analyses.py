"""Analyse / Reporting (cahier §8) : agrégations transverses (cloisonnées par direction).

Vise un vrai tableau analytique : KPI de pilotage (respect SLA, délai moyen de résolution,
retards), répartitions (module, priorité, direction, charge), matrice des risques
(probabilité × impact) et tendance hebdomadaire création vs résolution.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import AnalysesReponse
from dsi360.interface.securite import exiger_acces

routeur = APIRouter(prefix="/analyses", tags=["analyses"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces("analyses"))]

_JOINTURE = "FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id"
_OUVERTES = f"{_JOINTURE} WHERE a.cloture_le IS NULL"


async def _lignes(
    session: AsyncSession, requete: str, params: dict[str, Any]
) -> list[dict[str, Any]]:
    resultat = await session.execute(text(requete), params)
    return [dict(x) for x in resultat.mappings().all()]


@routeur.get("", response_model=AnalysesReponse)
async def analyses(courant: Courant, session: Session) -> dict[str, Any]:
    cond = ""
    params: dict[str, Any] = {}
    if not courant["transverse"]:
        cond = " AND d.code = :dir"
        params = {"dir": courant["direction"]}

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
        f"    AND a.cree_le < s.debut + interval '1 week'{cond}) AS crees, "
        f"  (SELECT count(*) {_JOINTURE} WHERE a.resolu_le >= s.debut "
        f"    AND a.resolu_le < s.debut + interval '1 week'{cond}) AS resolus "
        "FROM semaines s ORDER BY s.debut",
        params,
    )

    avec_sla = sla["a_lheure"] + sla["approche"] + sla["depasse"]
    respect = round(sla["a_lheure"] * 100 / avec_sla) if avec_sla > 0 else 100

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
        "matrice_risques": matrice_risques,
        "tendance": tendance,
    }

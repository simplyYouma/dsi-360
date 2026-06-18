"""Analyse / Reporting (cahier §8) : agrégations transverses (cloisonnées par direction)."""

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

_BASE = (
    "FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id "
    "WHERE a.cloture_le IS NULL"
)


@routeur.get("", response_model=AnalysesReponse)
async def analyses(courant: Courant, session: Session) -> dict[str, Any]:
    cond = ""
    params: dict[str, Any] = {}
    if not courant["transverse"]:
        cond = " AND d.code = :dir"
        params = {"dir": courant["direction"]}

    total = await session.scalar(text(f"SELECT count(*) {_BASE}{cond}"), params) or 0

    par_module = (
        await session.execute(
            text(f"SELECT a.module AS libelle, count(*) AS valeur {_BASE}{cond} GROUP BY a.module"),
            params,
        )
    ).mappings().all()

    par_direction = (
        await session.execute(
            text(
                f"SELECT coalesce(d.libelle, 'Non rattachée') AS libelle, count(*) AS valeur "
                f"{_BASE}{cond} GROUP BY d.libelle ORDER BY valeur DESC"
            ),
            params,
        )
    ).mappings().all()

    par_responsable = (
        await session.execute(
            text(
                f"SELECT (r.prenom || ' ' || r.nom) AS libelle, count(*) AS valeur "
                f"FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id "
                f"JOIN core.utilisateur r ON r.id = a.responsable_id "
                f"WHERE a.cloture_le IS NULL{cond} "
                f"GROUP BY r.id, r.prenom, r.nom ORDER BY valeur DESC LIMIT 8"
            ),
            params,
        )
    ).mappings().all()

    sla = (
        await session.execute(
            text(
                "SELECT "
                "count(*) FILTER (WHERE a.sla_resolution_le > now() + interval '2 hours') "
                "  AS a_lheure, "
                "count(*) FILTER (WHERE a.sla_resolution_le <= now() + interval '2 hours' "
                "  AND a.sla_resolution_le >= now()) AS approche, "
                "count(*) FILTER (WHERE a.sla_resolution_le < now()) AS depasse "
                f"{_BASE} AND a.sla_resolution_le IS NOT NULL{cond}"
            ),
            params,
        )
    ).mappings().one()

    return {
        "total": total,
        "par_module": [dict(x) for x in par_module],
        "par_direction": [dict(x) for x in par_direction],
        "par_responsable": [dict(x) for x in par_responsable],
        "sla": {
            "a_lheure": sla["a_lheure"],
            "approche": sla["approche"],
            "depasse": sla["depasse"],
        },
    }

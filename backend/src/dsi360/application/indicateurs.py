"""Indicateurs du tableau de bord : agrégations sur les activités (cloisonnées par direction)."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_CARTES = """
SELECT
  count(*) FILTER (WHERE a.module='incident' AND a.cloture_le IS NULL AND a.statut<>'Annulé')
    AS incidents_ouverts,
  count(*) FILTER (WHERE a.module='incident' AND a.priorite=1 AND a.cloture_le IS NULL)
    AS incidents_critiques,
  count(*) FILTER (WHERE a.module='demande' AND a.cloture_le IS NULL AND a.statut<>'Rejetée')
    AS demandes_en_cours,
  count(*) FILTER (WHERE a.module='projet' AND a.cloture_le IS NULL
    AND (a.donnees->>'date_fin') IS NOT NULL AND (a.donnees->>'date_fin')::date < current_date)
    AS projets_en_retard,
  count(*) FILTER (WHERE a.module='risque' AND a.cloture_le IS NULL) AS risques_critiques,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL) AS sla_total,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL
    AND a.sla_resolution_le >= now()) AS sla_ok,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL
    AND a.sla_resolution_le > now() + interval '2 hours') AS sla_a_lheure,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL
    AND a.sla_resolution_le <= now() + interval '2 hours' AND a.sla_resolution_le >= now())
    AS sla_approche,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL
    AND a.sla_resolution_le < now()) AS sla_depasse
FROM core.activite a
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE 1=1
"""

_REPARTITION = """
SELECT a.module AS module, count(*) AS valeur
FROM core.activite a
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.cloture_le IS NULL
"""


async def tableau_de_bord(session: AsyncSession, direction: str | None) -> dict[str, Any]:
    cond = " AND d.code = :dir" if direction is not None else ""
    params = {"dir": direction} if direction is not None else {}

    ligne = (await session.execute(text(_CARTES + cond), params)).mappings().one()
    total_sla = ligne["sla_total"] or 0
    respect = round(100 * (ligne["sla_ok"] or 0) / total_sla) if total_sla else 100

    repartition = (
        (await session.execute(text(_REPARTITION + cond + " GROUP BY a.module"), params))
        .mappings()
        .all()
    )

    return {
        "cartes": {
            "incidents_ouverts": ligne["incidents_ouverts"],
            "incidents_critiques": ligne["incidents_critiques"],
            "respect_sla": respect,
            "demandes_en_cours": ligne["demandes_en_cours"],
            "projets_en_retard": ligne["projets_en_retard"],
            "risques_critiques": ligne["risques_critiques"],
        },
        "sla": {
            "a_lheure": ligne["sla_a_lheure"],
            "approche": ligne["sla_approche"],
            "depasse": ligne["sla_depasse"],
        },
        "repartition": [{"module": r["module"], "valeur": r["valeur"]} for r in repartition],
    }

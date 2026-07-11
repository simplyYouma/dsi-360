"""Indicateurs du tableau de bord : agrégations sur les activités (cloisonnées par direction)."""

from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.activite import PREFIXE_REFERENCE
from dsi360.domain.etats import STATUTS_TERMINAUX, etats_terminaux

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
  count(*) FILTER (WHERE a.module='risque' AND a.cloture_le IS NULL
    AND nullif(a.donnees->>'criticite','')::int >= 4) AS risques_critiques,
  count(*) FILTER (WHERE a.module='risque' AND a.cloture_le IS NULL) AS risques_ouverts,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL) AS sla_total,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL
    AND a.sla_resolution_le >= now()) AS sla_ok,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL
    AND a.sla_resolution_le > now() + interval '2 hours') AS sla_a_lheure,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL
    AND a.sla_resolution_le <= now() + interval '2 hours' AND a.sla_resolution_le >= now())
    AS sla_approche,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL
    AND a.sla_resolution_le < now()) AS sla_depasse,
  count(*) FILTER (WHERE a.source='IMPORT_SD'
    AND nullif(a.donnees->>'ttr_minutes','')::numeric > 0) AS sla_reel_total,
  count(*) FILTER (WHERE a.source='IMPORT_SD'
    AND nullif(a.donnees->>'ttr_minutes','')::numeric > 0
    AND nullif(a.donnees->>'ttr_minutes','')::numeric <= sr.resolution_minutes) AS sla_reel_ok
FROM core.activite a
LEFT JOIN core.direction d ON d.id = a.direction_id
LEFT JOIN core.sla_regle sr ON sr.priorite = a.priorite AND sr.module = a.module
WHERE 1=1
"""

_REPARTITION = """
SELECT a.module AS module, count(*) AS valeur
FROM core.activite a
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.cloture_le IS NULL
"""

# Tendance hebdomadaire (8 dernières semaines) des activités par état SLA courant.
_SERIE = """
SELECT to_char(date_trunc('week', a.cree_le), 'DD/MM') AS periode,
  count(*) FILTER (WHERE a.sla_resolution_le > now() + interval '2 hours') AS a_lheure,
  count(*) FILTER (WHERE a.sla_resolution_le <= now() + interval '2 hours'
    AND a.sla_resolution_le >= now()) AS approche,
  count(*) FILTER (WHERE a.sla_resolution_le < now()) AS depasse
FROM core.activite a
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.sla_resolution_le IS NOT NULL AND a.cree_le >= now() - interval '8 weeks'
"""


# Les activités à traiter en premier : échéance la plus proche (ou la plus dépassée) d'abord.
# C'est la réponse à « alertes, activités en retard » du cahier — un chiffre alarmant doit mener
# aux dossiers qui le composent.
_A_TRAITER = """
SELECT a.module, a.id::text AS id, a.reference, a.titre, a.priorite, a.statut,
       a.sla_resolution_le
FROM core.activite a
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.cloture_le IS NULL AND a.resolu_le IS NULL AND a.sla_resolution_le IS NOT NULL
  AND a.statut NOT IN :statuts_regles
"""

# Un ticket résolu, clôturé, rejeté ou annulé n'attend plus personne : il ne se traite pas.
_TERMINAUX = sorted({e for m in PREFIXE_REFERENCE for e in etats_terminaux(m)})
# Ce qui ne réclame plus de travail (résolu compris), pour la file « À traiter ».
_STATUTS_REGLES = sorted(STATUTS_TERMINAUX)

# Créations hebdomadaires des tickets importés : la respiration du flux, en miniature.
_CREATIONS_HEBDO = """
WITH semaines AS (
  SELECT generate_series(date_trunc('week', now()) - interval '7 weeks',
                         date_trunc('week', now()), interval '1 week') AS debut)
SELECT s.debut, m.module,
  (SELECT count(*) FROM core.activite a
    WHERE a.module = m.module AND a.cree_le >= s.debut
      AND a.cree_le < s.debut + interval '1 week') AS valeur
FROM semaines s CROSS JOIN (VALUES ('incident'), ('demande')) AS m(module)
ORDER BY s.debut
"""

_DBS_DASH = """
SELECT count(*) FILTER (WHERE a.responsable_id IS NULL AND a.cloture_le IS NULL) AS dbs_ouverts,
       round((avg(extract(epoch FROM now() - a.cree_le) / 86400)
         FILTER (WHERE a.responsable_id IS NULL AND a.cloture_le IS NULL))::numeric, 1)
         AS dbs_age_jours
FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.source = 'IMPORT_SD'
"""

_ROUVERTS_30J = """
SELECT count(DISTINCT j.cible_id) FROM audit.journal j
WHERE j.action = 'TRANSITION' AND j.nouvelle_valeur->>'statut' = 'Réouvert'
  AND j.horodatage >= now() - interval '30 days'
"""

_RESOLUS_30J = """
SELECT count(*) FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.resolu_le >= now() - interval '30 days'
"""


async def tableau_de_bord(session: AsyncSession, direction: str | None) -> dict[str, Any]:
    cond = " AND d.code = :dir" if direction is not None else ""
    params = {"dir": direction} if direction is not None else {}

    ligne = (await session.execute(text(_CARTES + cond), params)).mappings().one()
    # Respect SLA réel (durées mesurées des tickets importés) ; repli sur les échéances en cours.
    reel_total = ligne["sla_reel_total"] or 0
    total_sla = ligne["sla_total"] or 0
    if reel_total:
        respect = round(100 * (ligne["sla_reel_ok"] or 0) / reel_total)
    elif total_sla:
        respect = round(100 * (ligne["sla_ok"] or 0) / total_sla)
    else:
        respect = 100

    repartition = (
        (await session.execute(text(_REPARTITION + cond + " GROUP BY a.module"), params))
        .mappings()
        .all()
    )

    serie = (
        (
            await session.execute(
                text(
                    _SERIE
                    + cond
                    + " GROUP BY date_trunc('week', a.cree_le)"
                    + " ORDER BY date_trunc('week', a.cree_le)"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    requete_a_traiter = text(
        _A_TRAITER + cond + " ORDER BY a.sla_resolution_le ASC LIMIT 6"
    ).bindparams(bindparam("statuts_regles", expanding=True))
    a_traiter = (
        (await session.execute(requete_a_traiter, {**params, "statuts_regles": _STATUTS_REGLES}))
        .mappings()
        .all()
    )

    creations = (await session.execute(text(_CREATIONS_HEBDO))).mappings().all()
    creations_hebdo: dict[str, list[int]] = {"incident": [], "demande": []}
    for c in creations:
        creations_hebdo[c["module"]].append(c["valeur"])

    dbs = (await session.execute(text(_DBS_DASH + cond), params)).mappings().one()
    rouverts = await session.scalar(text(_ROUVERTS_30J)) or 0
    resolus_30j = await session.scalar(text(_RESOLUS_30J + cond), params) or 0

    return {
        "a_traiter": [dict(x) for x in a_traiter],
        "creations_hebdo": creations_hebdo,
        "dbs_ouverts": dbs["dbs_ouverts"],
        "dbs_age_jours": float(dbs["dbs_age_jours"]) if dbs["dbs_age_jours"] is not None else None,
        "rouverts_30j": rouverts,
        "resolus_30j": resolus_30j,
        "cartes": {
            "incidents_ouverts": ligne["incidents_ouverts"],
            "incidents_critiques": ligne["incidents_critiques"],
            "respect_sla": respect,
            "demandes_en_cours": ligne["demandes_en_cours"],
            "projets_en_retard": ligne["projets_en_retard"],
            "risques_critiques": ligne["risques_critiques"],
            "risques_ouverts": ligne["risques_ouverts"],
        },
        "sla": {
            "a_lheure": ligne["sla_a_lheure"],
            "approche": ligne["sla_approche"],
            "depasse": ligne["sla_depasse"],
        },
        "repartition": [{"module": r["module"], "valeur": r["valeur"]} for r in repartition],
        "serie": [
            {
                "periode": s["periode"],
                "a_lheure": s["a_lheure"],
                "approche": s["approche"],
                "depasse": s["depasse"],
            }
            for s in serie
        ],
    }

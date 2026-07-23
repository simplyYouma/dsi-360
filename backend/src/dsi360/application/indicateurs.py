"""Indicateurs du tableau de bord : agrégations sur les activités (cloisonnées par direction)."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.granularite_temps import (
    FMT_SQL,
    UNIT_SQL,
    ajouter,
    cle_bucket,
    granularite,
    libelle_bucket,
    suite_buckets,
)
from dsi360.domain.activite import PREFIXE_REFERENCE
from dsi360.domain.etats import etats_terminaux
from dsi360.infrastructure import phases_sql


def _clause_periode(
    jours: int | None, du: date | None, au: date | None
) -> tuple[str, dict[str, Any]]:
    """Filtre sur la date de création. Priorité : dates explicites > jours > tout (chaîne vide)."""
    if du is not None or au is not None:
        cond, params = "", {}
        if du is not None:
            cond += " AND a.cree_le >= :du"
            params["du"] = du
        if au is not None:
            cond += " AND a.cree_le < (cast(:au as date) + 1)"
            params["au"] = au
        return cond, params
    if jours is not None:
        return " AND a.cree_le >= now() - make_interval(days => :jours)", {"jours": jours}
    return "", {}

# Un dossier terminé ne court plus après son délai : seul ce qui est en cours peut être en retard.
_EN_COURS = phases_sql.en_cours()

# Cartes du tableau de bord : un ÉTAT GÉNÉRAL, transverse à tous les modules (pas centré incidents).
_CARTES = f"""
SELECT
  -- « Ouvert » = la phase du domaine, jamais l'absence de date de clôture ni une liste de
  -- statuts écrite ici. « Résolu », « Réalisé », « Maîtrisé », « Corrigé » ne posent aucun
  -- `cloture_le` : comptés sur l'horodatage, ces dossiers finis gonflaient la carte, qui ne
  -- s'accordait plus avec les compteurs des listes.
  count(*) FILTER (WHERE {_EN_COURS}) AS activites_ouvertes,
  count(*) FILTER (WHERE {_EN_COURS}
    AND (a.priorite = 1 OR nullif(a.donnees->>'criticite','')::int >= 4)) AS critiques,
  count(*) FILTER (WHERE {_EN_COURS} AND a.responsable_id IS NOT NULL) AS charge_dsi,
  count(*) FILTER (WHERE {_EN_COURS}
    AND a.sla_resolution_le IS NOT NULL AND a.sla_resolution_le < now()) AS en_retard,
  count(*) FILTER (WHERE a.resolu_le IS NOT NULL OR a.cloture_le IS NOT NULL) AS resolues,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL) AS sla_total,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND a.cloture_le IS NULL
    AND a.sla_resolution_le >= now()) AS sla_ok,
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

# Tendance des activités ouvertes par état SLA courant, regroupées par bucket de temps. La
# granularité (jour/mois/année) suit la période choisie, comme la synthèse des analyses.
_SERIE = f"""
SELECT to_char(date_trunc('{{trunc}}', a.cree_le), '{{fmt}}') AS bucket,
  count(*) FILTER (WHERE a.sla_resolution_le > now() + interval '2 hours') AS a_lheure,
  count(*) FILTER (WHERE a.sla_resolution_le <= now() + interval '2 hours'
    AND a.sla_resolution_le >= now()) AS approche,
  count(*) FILTER (WHERE a.sla_resolution_le < now()) AS depasse
FROM core.activite a
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.sla_resolution_le IS NOT NULL AND {_EN_COURS}
  AND a.cree_le >= :s_debut AND a.cree_le < :s_fin
"""


# Les activités à traiter en premier : échéance la plus proche (ou la plus dépassée) d'abord.
# C'est la réponse à « alertes, activités en retard » du cahier — un chiffre alarmant doit mener
# aux dossiers qui le composent.
_A_TRAITER = f"""
SELECT a.module, a.id::text AS id, a.reference, a.titre, a.priorite, a.statut,
       a.sla_resolution_le
FROM core.activite a
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE {_EN_COURS} AND a.sla_resolution_le IS NOT NULL
"""

# Un ticket résolu, clôturé, rejeté ou annulé n'attend plus personne : il ne se traite pas.
_TERMINAUX = sorted({e for m in PREFIXE_REFERENCE for e in etats_terminaux(m)})

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

# Chez DBS : un gestionnaire est nommé, mais aucun de nos comptes (ADR-0005). Sans nom renseigné,
# le ticket n'est chez personne — il ne gonfle donc pas le compteur DBS.
_EST_DBS = "(a.responsable_id IS NULL AND nullif(trim(a.donnees->>'gestionnaire'), '') IS NOT NULL)"

_DBS_DASH = f"""
SELECT count(*) FILTER (WHERE {_EST_DBS} AND a.cloture_le IS NULL) AS dbs_ouverts,
       round((avg(extract(epoch FROM now() - a.cree_le) / 86400)
         FILTER (WHERE {_EST_DBS} AND a.cloture_le IS NULL))::numeric, 1)
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

# Signaux « état courant » (jamais filtrés par période) : stock qui traîne, tickets en attente de
# prise en charge, ET la répartition SLA du stock ouvert (à l'heure / approche / dépassé). Ces
# derniers alimentent le signal « Échéances dépassées » et la légende de la tendance : ils doivent
# refléter le maintenant, pas la fenêtre de création (sinon on masque les vieux dossiers en retard).
_SIGNAUX = f"""
SELECT
  count(*) FILTER (WHERE a.cloture_le IS NULL) AS ouverts_total,
  count(*) FILTER (WHERE {_EN_COURS}
    AND a.cree_le < now() - interval '30 days') AS ouverts_30j,
  count(*) FILTER (WHERE {_EN_COURS}
    AND a.pris_en_charge_le IS NULL) AS non_pris_en_charge,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND {_EN_COURS}
    AND a.sla_resolution_le > now() + interval '2 hours') AS a_lheure,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND {_EN_COURS}
    AND a.sla_resolution_le <= now() + interval '2 hours'
    AND a.sla_resolution_le >= now()) AS approche,
  count(*) FILTER (WHERE a.sla_resolution_le IS NOT NULL AND {_EN_COURS}
    AND a.sla_resolution_le < now()) AS depasse
FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE 1=1
"""


async def tableau_de_bord(
    session: AsyncSession,
    direction: str | None,
    jours: int | None = None,
    du: date | None = None,
    au: date | None = None,
) -> dict[str, Any]:
    cond = " AND d.code = :dir" if direction is not None else ""
    params: dict[str, Any] = {"dir": direction} if direction is not None else {}
    # Filtre période (sur la date de création) : appliqué aux KPI et graphes analytiques (cond_p).
    # Les files d'urgence (« À traiter ») et les signaux courants (DBS) gardent `cond` seul : les
    # filtrer par date de création masquerait les vieux dossiers en retard, l'inverse du besoin.
    perio, perio_params = _clause_periode(jours, du, au)
    cond_p = cond + perio
    params.update(perio_params)

    ligne = (await session.execute(text(_CARTES + cond_p), params)).mappings().one()
    # Respect SLA réel (durées mesurées des tickets importés) ; repli sur les échéances en cours.
    # `respect_base` = taille de l'échantillon réellement mesuré (le front neutralise un 100 % sur
    # trop peu de cas, comme ailleurs).
    reel_total = ligne["sla_reel_total"] or 0
    total_sla = ligne["sla_total"] or 0
    if reel_total:
        respect = round(100 * (ligne["sla_reel_ok"] or 0) / reel_total)
        respect_base = reel_total
    elif total_sla:
        respect = round(100 * (ligne["sla_ok"] or 0) / total_sla)
        respect_base = total_sla
    else:
        respect = 100
        respect_base = 0

    repartition = (
        (await session.execute(text(_REPARTITION + cond_p + " GROUP BY a.module"), params))
        .mappings()
        .all()
    )

    # Tendance : sur la période demandée, à la granularité jour/mois/année (comme la synthèse) ; à
    # défaut (« Tout »), fenêtre glissante de 30 jours pour garder une courbe lisible.
    maintenant = datetime.now(UTC)
    if du is not None or au is not None:
        s_debut = datetime(du.year, du.month, du.day, tzinfo=UTC) if du else maintenant
        s_fin = datetime(au.year, au.month, au.day, tzinfo=UTC) if au else maintenant
    elif jours is not None:
        s_debut, s_fin = maintenant - timedelta(days=jours), maintenant
    else:
        s_debut, s_fin = maintenant - timedelta(days=30), maintenant
    unit = granularite(max(0, (s_fin - s_debut).days))
    seaux = suite_buckets(unit, s_debut, s_fin)
    sparams = {**params, "s_debut": seaux[0], "s_fin": ajouter(unit, seaux[-1])}
    lignes_serie = (
        (
            await session.execute(
                text(_SERIE.format(trunc=UNIT_SQL[unit], fmt=FMT_SQL[unit]) + cond + " GROUP BY 1"),
                sparams,
            )
        )
        .mappings()
        .all()
    )
    par_bucket = {r["bucket"]: r for r in lignes_serie}
    serie = []
    for b in seaux:
        r = par_bucket.get(cle_bucket(unit, b))
        serie.append(
            {
                "periode": libelle_bucket(unit, b),
                "a_lheure": r["a_lheure"] if r else 0,
                "approche": r["approche"] if r else 0,
                "depasse": r["depasse"] if r else 0,
            }
        )

    a_traiter = (
        (
            await session.execute(
                text(_A_TRAITER + cond + " ORDER BY a.sla_resolution_le ASC LIMIT 6"), params
            )
        )
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
    # Signaux d'état courant : on garde `cond` (direction seule), pas la période.
    sig = (await session.execute(text(_SIGNAUX + cond), params)).mappings().one()

    return {
        "a_traiter": [dict(x) for x in a_traiter],
        "creations_hebdo": creations_hebdo,
        "dbs_ouverts": dbs["dbs_ouverts"],
        "dbs_age_jours": float(dbs["dbs_age_jours"]) if dbs["dbs_age_jours"] is not None else None,
        "rouverts_30j": rouverts,
        "resolus_30j": resolus_30j,
        "ouverts_30j": sig["ouverts_30j"],
        "non_pris_en_charge": sig["non_pris_en_charge"],
        "ouverts_total": sig["ouverts_total"],
        "cartes": {
            "activites_ouvertes": ligne["activites_ouvertes"],
            "critiques": ligne["critiques"],
            "charge_dsi": ligne["charge_dsi"],
            "en_retard": ligne["en_retard"],
            "resolues": ligne["resolues"],
            "respect_sla": respect,
            "respect_sla_base": respect_base,
        },
        # Répartition SLA du stock ouvert MAINTENANT (état courant, jamais filtré par période) :
        # alimente le signal « Échéances dépassées » et la légende de la tendance.
        "sla": {
            "a_lheure": sig["a_lheure"],
            "approche": sig["approche"],
            "depasse": sig["depasse"],
        },
        "repartition": [{"module": r["module"], "valeur": r["valeur"]} for r in repartition],
        "serie": serie,
    }

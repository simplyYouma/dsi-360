"""Analyse / Reporting (cahier §8) : agrégations transverses (cloisonnées par direction).

Vise un vrai tableau analytique : KPI de pilotage (respect SLA, délai moyen de résolution,
retards), répartitions (module, priorité, direction, charge), matrice des risques
(probabilité × impact) et tendance hebdomadaire création vs résolution.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.granularite_temps import FMT_SQL as _FMT_SQL
from dsi360.application.granularite_temps import UNIT_SQL as _UNIT_SQL
from dsi360.application.granularite_temps import ajouter as _ajouter
from dsi360.application.granularite_temps import cle_bucket as _cle_bucket
from dsi360.application.granularite_temps import granularite as _granularite
from dsi360.application.granularite_temps import libelle_bucket as _libelle_bucket
from dsi360.application.granularite_temps import tronquer as _tronquer
from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import (
    AnalysesMensuelles,
    AnalysesReponse,
    GestionnaireDetail,
    GestionnaireEval,
)
from dsi360.interface.securite import exiger_acces

routeur = APIRouter(prefix="/analyses", tags=["analyses"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces("analyses"))]

_MODULE_LABEL = {
    "incident": "Incidents",
    "demande": "Demandes",
    "projet": "Projets",
    "changement": "Changements",
    "audit": "Audit",
    "risque": "Risques",
    "cybersecurite": "Cybersecurite",
    "gouvernance": "Gouvernance",
}

_JOINTURE = "FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id"
_OUVERTES = f"{_JOINTURE} WHERE a.cloture_le IS NULL"

# Cible de résolution = règle SLA paramétrable (core.sla_regle), jointe sur la priorité.
_CIBLE = "sr.resolution_minutes"
_TTR = "nullif(a.donnees->>'ttr_minutes', '')::numeric"
# Population SLA réelle : tickets importés effectivement résolus (durée mesurée > 0).
_RESOLUS = (
    f"{_JOINTURE} JOIN core.sla_regle sr ON sr.priorite = a.priorite AND sr.module = a.module "
    f"WHERE a.source = 'IMPORT_SD' AND a.priorite IS NOT NULL AND {_TTR} > 0"
)


# Temps moyen passé dans chaque statut : séjours *terminés*, reconstitués du journal d'audit.
# Un séjour encore ouvert n'est pas compté — il gonflerait la moyenne à mesure qu'on la regarde.
_DUREES_STATUTS = """
WITH pas AS (
  SELECT j.module, j.cible_id, j.nouvelle_valeur->>'statut' AS statut, j.horodatage,
         lead(j.horodatage) OVER (PARTITION BY j.module, j.cible_id ORDER BY j.id) AS fin
  FROM audit.journal j
  WHERE j.action IN ('CREATION','TRANSITION') AND j.nouvelle_valeur->>'statut' IS NOT NULL
)
SELECT p.module, p.statut,
       round((avg(extract(epoch FROM (p.fin - p.horodatage)) / 86400))::numeric, 1) AS jours,
       count(*) AS passages
FROM pas p WHERE p.fin IS NOT NULL{periode}
GROUP BY p.module, p.statut HAVING count(*) > 0
"""

# Réouvertures lues dans le journal : le statut courant oublie un ticket rouvert puis résolu.
_ROUVERTS = """
SELECT j.module AS libelle, count(DISTINCT j.cible_id) AS rouverts
FROM audit.journal j
WHERE j.action = 'TRANSITION' AND j.nouvelle_valeur->>'statut' = 'Réouvert'{periode}
GROUP BY j.module
"""

_RESOLUS_PAR_MODULE = """
SELECT a.module AS libelle, count(*) AS resolus
FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE (a.resolu_le IS NOT NULL OR a.cloture_le IS NOT NULL){cond}
GROUP BY a.module
"""

# Vieillissement du stock ouvert : instantané, la période ne s'y applique pas.
_VIEILLISSEMENT = """
SELECT b.libelle, count(a.id) AS valeur
FROM (VALUES ('≤ 7 j', 0, 7), ('8–30 j', 7, 30), ('31–90 j', 30, 90), ('> 90 j', 90, 100000))
     AS b(libelle, de, jusqu_a)
LEFT JOIN core.activite a ON a.cloture_le IS NULL AND a.cree_le IS NOT NULL
  AND extract(epoch FROM now() - a.cree_le) / 86400 > b.de
  AND extract(epoch FROM now() - a.cree_le) / 86400 <= b.jusqu_a
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE TRUE{cond_dir}
GROUP BY b.libelle, b.de ORDER BY b.de
"""

# Chez DBS : un gestionnaire est nommé, mais ce n'est aucun de nos comptes (ADR-0005). Sans nom
# renseigné, le ticket n'est chez personne — surtout pas chez DBS. L'import normalise les absences
# écrites en toutes lettres (« None », « N/A »…) : ici, tester la présence suffit.
_EST_DBS = "(a.responsable_id IS NULL AND nullif(trim(a.donnees->>'gestionnaire'), '') IS NOT NULL)"
# Entité qui traite le ticket : nous (DSI), DBS, ou personne (NR = non renseigné).
_ENTITE_SQL = (
    "CASE WHEN a.responsable_id IS NOT NULL THEN 'DSI' "
    f"WHEN {_EST_DBS} THEN 'DBS' ELSE 'NR' END"
)

# DSI vs DBS (tickets importés).
_DBS = f"""
SELECT count(*) FILTER (WHERE a.responsable_id IS NOT NULL) AS dsi,
       count(*) FILTER (WHERE {_EST_DBS}) AS dbs,
       count(*) FILTER (WHERE {_EST_DBS} AND a.cloture_le IS NULL) AS dbs_ouverts,
       round((avg(extract(epoch FROM now() - a.cree_le) / 86400)
         FILTER (WHERE {_EST_DBS} AND a.cloture_le IS NULL))::numeric, 1)
         AS dbs_age_jours
FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.source = 'IMPORT_SD'{{cond}}
"""

# Pareto des catégories : ce qui casse le plus, en volume et en part cumulée.
_PARETO = """
SELECT c.libelle, count(*) AS valeur
FROM core.activite a
JOIN core.categorie c ON c.id = a.categorie_id
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE TRUE{cond}
GROUP BY c.libelle ORDER BY valeur DESC, c.libelle
"""

# Ordre fixe des tranches de délai de résolution (l'histogramme se lit du plus rapide au plus lent).
_ORDRE_DELAI = ["< 4 h", "< 1 j", "1–3 j", "3–7 j", "> 7 j"]

_TREP = "nullif(a.donnees->>'ttrespond_minutes', '')::numeric"

# Prise en charge : la première moitié de l'engagement SLA, jamais mesurée jusqu'ici.
_PEC_PRIORITE = """
SELECT a.priorite AS niveau, count(*) AS total,
       count(*) FILTER (WHERE {trep} <= sr.prise_en_charge_minutes) AS dans_delai
FROM core.activite a
JOIN core.sla_regle sr ON sr.priorite = a.priorite AND sr.module = a.module
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.source = 'IMPORT_SD' AND a.priorite IS NOT NULL AND {trep} > 0{cond}
GROUP BY a.priorite ORDER BY a.priorite
"""

# Activités suivies comme contributeur : elles entrent dans la file de l'agent (ADR-0005 §5).
_SUIVIS = """
SELECT aa.utilisateur_id::text AS id, count(*) AS suivis
FROM core.activite_acteur aa JOIN core.activite a ON a.id = aa.activite_id
WHERE aa.role = 'CONTRIBUTEUR'{periode}
GROUP BY aa.utilisateur_id
"""


def _taux(part: int, total: int) -> int:
    return round(part * 100 / total) if total else 0


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
    du: date | None = None,
    au: date | None = None,
) -> dict[str, Any]:
    cond_dir = ""
    params: dict[str, Any] = dict(_pparams(jours, du, au))
    if not courant["transverse"]:
        # Activité sans direction (tickets importés : l'import n'en pose pas) = visible par tous,
        # comme dans les listes et `_visible`. Sinon le tableau de bord d'un agent non transverse
        # ignorerait tous les incidents/demandes importés.
        cond_dir = " AND (d.code = :dir OR a.direction_id IS NULL)"
        params["dir"] = courant["direction"]
    # Filtre période (sur la date de création) appliqué aux agrégations, hors tendance.
    cond = cond_dir + _periode(jours, du, au)

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

    # MTTR : délai moyen de résolution (jours), sur la période (par date de création).
    mttr = await session.scalar(
        text(
            "SELECT round(avg(extract(epoch FROM (a.resolu_le - a.cree_le)) / 86400)::numeric, 1) "
            f"{_JOINTURE} WHERE a.resolu_le IS NOT NULL{cond}"
        ),
        params,
    )

    # La tendance suit la période choisie, avec la même granularité que la synthèse : jour (nom du
    # jour), mois ou année selon l'étendue. L'axe et les libellés sont donc cohérents entre onglets.
    maintenant = datetime.now(UTC)
    if du is not None or au is not None:
        t_debut = datetime(du.year, du.month, du.day, tzinfo=UTC) if du else maintenant
        t_fin = datetime(au.year, au.month, au.day, tzinfo=UTC) if au else maintenant
    elif jours is not None:
        t_debut, t_fin = maintenant - timedelta(days=jours), maintenant
    else:
        # « Tout » : on cadre sur l'étendue réelle des données importées (repli 12 mois si vide).
        bornes = (await session.execute(text(_PLAGE_IMPORT.format(cond=cond_dir)), params)).first()
        t_debut = (bornes.mini if bornes is not None else None) or (
            maintenant - timedelta(days=365)
        )
        t_fin = (bornes.maxi if bornes is not None else None) or maintenant

    unit = _granularite(max(0, (t_fin - t_debut).days))
    trunc, fmt = _UNIT_SQL[unit], _FMT_SQL[unit]
    b_dep, b_der = _tronquer(unit, t_debut), _tronquer(unit, t_fin)
    seaux: list[datetime] = []
    b_cur = b_dep
    while b_cur <= b_der and len(seaux) < 400:
        seaux.append(b_cur)
        b_cur = _ajouter(unit, b_cur)
    if not seaux:
        seaux = [b_dep]
    tparams: dict[str, Any] = {"t_debut": seaux[0], "t_fin": _ajouter(unit, seaux[-1])}
    if "dir" in params:
        tparams["dir"] = params["dir"]
    crees_par = {
        r["bucket"]: r["n"]
        for r in await _lignes(
            session,
            f"SELECT to_char(date_trunc('{trunc}', a.cree_le), '{fmt}') AS bucket, count(*) AS n "
            f"{_JOINTURE} WHERE a.cree_le >= :t_debut AND a.cree_le < :t_fin{cond_dir} GROUP BY 1",
            tparams,
        )
    }
    resolus_par = {
        r["bucket"]: r["n"]
        for r in await _lignes(
            session,
            f"SELECT to_char(date_trunc('{trunc}', a.resolu_le), '{fmt}') AS bucket, count(*) AS n "
            f"{_JOINTURE} WHERE a.resolu_le >= :t_debut AND a.resolu_le < :t_fin{cond_dir} "
            "GROUP BY 1",
            tparams,
        )
    }
    tendance = [
        {
            "periode": _libelle_bucket(unit, b),
            "crees": crees_par.get(_cle_bucket(unit, b), 0),
            "resolus": resolus_par.get(_cle_bucket(unit, b), 0),
        }
        for b in seaux
    ]

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

    # Le filtre porte sur l'horodatage du journal, mais l'alias diffère : la requête des durées
    # trie depuis le CTE `pas p` (p.horodatage), celle des réouvertures depuis `journal j`.
    durees_statuts = await _lignes(
        session,
        _DUREES_STATUTS.format(periode=_periode(jours, du, au, "p.horodatage")),
        params,
    )

    rouverts = {
        r["libelle"]: r["rouverts"]
        for r in await _lignes(
            session, _ROUVERTS.format(periode=_periode(jours, du, au, "j.horodatage")), params
        )
    }
    resolus_mod = await _lignes(session, _RESOLUS_PAR_MODULE.format(cond=cond), params)
    reouvertures = [
        {
            "libelle": r["libelle"],
            "rouverts": rouverts.get(r["libelle"], 0),
            "resolus": r["resolus"],
            "taux": _taux(rouverts.get(r["libelle"], 0), r["resolus"]),
        }
        for r in resolus_mod
        if r["resolus"] > 0 or rouverts.get(r["libelle"], 0) > 0
    ]

    # Vieillissement : INSTANTANÉ de l'âge du stock ouvert (jamais filtré par période — filtrer sur
    # la date de création ferait disparaître le vieux stock, l'inverse du but du visuel).
    vieillissement = await _lignes(session, _VIEILLISSEMENT.format(cond_dir=cond_dir), params)

    ligne_dbs = (await session.execute(text(_DBS.format(cond=cond)), params)).mappings().one()
    dbs = {
        "dsi": ligne_dbs["dsi"],
        "dbs": ligne_dbs["dbs"],
        "dbs_ouverts": ligne_dbs["dbs_ouverts"],
        "dbs_age_jours": float(ligne_dbs["dbs_age_jours"])
        if ligne_dbs["dbs_age_jours"] is not None
        else None,
    }

    categories = await _lignes(session, _PARETO.format(cond=cond), params)
    total_cat = sum(c["valeur"] for c in categories)
    pareto, cumul = [], 0
    for c in categories[:8]:
        cumul += c["valeur"]
        pareto.append(
            {"libelle": c["libelle"], "valeur": c["valeur"], "cumul_pct": _taux(cumul, total_cat)}
        )

    pec = await _lignes(session, _PEC_PRIORITE.format(trep=_TREP, cond=cond), params)
    pec_par_priorite = [
        {
            "priorite": f"P{x['niveau']}",
            "dans_delai": x["dans_delai"],
            "total": x["total"],
            "taux": _taux(x["dans_delai"], x["total"]),
        }
        for x in pec
    ]

    # Distribution des délais de résolution : la dispersion réelle, au-delà de la moyenne (MTTR).
    tranches = await _lignes(
        session,
        "SELECT CASE "
        "WHEN a.resolu_le - a.cree_le < interval '4 hours' THEN '< 4 h' "
        "WHEN a.resolu_le - a.cree_le < interval '1 day' THEN '< 1 j' "
        "WHEN a.resolu_le - a.cree_le < interval '3 days' THEN '1–3 j' "
        "WHEN a.resolu_le - a.cree_le < interval '7 days' THEN '3–7 j' "
        "ELSE '> 7 j' END AS libelle, count(*) AS valeur "
        f"{_JOINTURE} WHERE a.resolu_le IS NOT NULL{cond} GROUP BY 1",
        params,
    )
    par_tranche = {t["libelle"]: t["valeur"] for t in tranches}
    distribution_delais = [
        {"libelle": lib, "valeur": par_tranche.get(lib, 0)} for lib in _ORDRE_DELAI
    ]

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
        "durees_statuts": durees_statuts,
        "reouvertures": reouvertures,
        "vieillissement": vieillissement,
        "distribution_delais": distribution_delais,
        "dbs": dbs,
        "pareto_categories": pareto,
        "pec_par_priorite": pec_par_priorite,
    }


# Filtre période injectable, sur `colonne`. Dates explicites (du/au) prioritaires sur le nombre de
# jours. `_periode` donne le SQL ; `_pparams` les paramètres liés (clés :du/:au/:jours).
def _periode(
    jours: int | None, du: date | None, au: date | None, colonne: str = "a.cree_le"
) -> str:
    if du is not None or au is not None:
        sql = ""
        if du is not None:
            sql += f" AND {colonne} >= :du"
        if au is not None:
            sql += f" AND {colonne} < (cast(:au as date) + 1)"
        return sql
    return f" AND {colonne} >= now() - make_interval(days => :jours)" if jours is not None else ""


def _pparams(jours: int | None, du: date | None, au: date | None) -> dict[str, Any]:
    if du is not None or au is not None:
        p: dict[str, Any] = {}
        if du is not None:
            p["du"] = du
        if au is not None:
            p["au"] = au
        return p
    return {"jours": jours} if jours is not None else {}


_AGREGATS_GEST = (
    "count(*) AS volume, "
    "count(*) FILTER (WHERE s.cloture_le IS NULL) AS charge, "
    "count(*) FILTER (WHERE s.resolu_le IS NOT NULL OR s.cloture_le IS NOT NULL) AS resolus, "
    "round(avg(s.ttr) FILTER (WHERE s.ttr > 0) / 1440.0, 1) AS mttr_jours, "
    "round(avg(s.trep) FILTER (WHERE s.trep > 0) / 60.0, 1) AS prise_en_charge_h, "
    # Respect SLA : parmi les tickets à durée mesurée et cible connue, part résolue à temps.
    "count(*) FILTER (WHERE s.ttr > 0 AND s.cible IS NOT NULL) AS base_sla, "
    "count(*) FILTER (WHERE s.ttr > 0 AND s.cible IS NOT NULL AND s.ttr <= s.cible) AS sla_ok"
)


def _src_gest(extra: str) -> str:
    return (
        "SELECT r.id::text AS id, r.prenom, r.nom, a.cloture_le, a.resolu_le, "
        "  nullif(a.donnees->>'ttr_minutes', '')::numeric AS ttr, "
        "  nullif(a.donnees->>'ttrespond_minutes', '')::numeric AS trep, "
        "  sr.resolution_minutes AS cible "
        "FROM core.activite a JOIN core.utilisateur r ON r.id = a.responsable_id "
        "  LEFT JOIN core.sla_regle sr ON sr.priorite = a.priorite AND sr.module = a.module "
        f"WHERE a.source = 'IMPORT_SD'{extra}"
    )


def _eval_dict(r: Any) -> dict[str, Any]:
    return {
        "id": r["id"],
        "gestionnaire": r["gestionnaire"],
        "volume": r["volume"],
        "charge": r["charge"],
        "resolus": r["resolus"],
        "mttr_jours": float(r["mttr_jours"]) if r["mttr_jours"] is not None else None,
        "prise_en_charge_h": float(r["prise_en_charge_h"])
        if r["prise_en_charge_h"] is not None
        else None,
        "respect_sla": round(int(r["sla_ok"]) * 100 / int(r["base_sla"]))
        if r["base_sla"]
        else None,
    }


@routeur.get("/gestionnaires", response_model=list[GestionnaireEval])
async def evaluation_gestionnaires(
    courant: Courant,
    session: Session,
    jours: Annotated[int | None, Query(ge=1, le=3650)] = None,
    du: date | None = None,
    au: date | None = None,
) -> list[dict[str, Any]]:
    requete = (
        f"SELECT s.id, (s.prenom || ' ' || s.nom) AS gestionnaire, {_AGREGATS_GEST} "
        f"FROM ({_src_gest(_periode(jours, du, au))}) s "
        "GROUP BY s.id, s.prenom, s.nom ORDER BY volume DESC LIMIT 20"
    )
    params = _pparams(jours, du, au)
    lignes = (await session.execute(text(requete), params)).mappings().all()
    evaluations = [_eval_dict(r) for r in lignes]

    # Les activités suivies comme contributeur comptent dans les statistiques de l'agent —
    # y compris pour un agent qui ne gère rien : il apparaît alors avec un volume nul.
    suivis = {
        r["id"]: r["suivis"]
        for r in await _lignes(session, _SUIVIS.format(periode=_periode(jours, du, au)), params)
    }
    for e in evaluations:
        e["suivis"] = suivis.pop(e["id"], 0)
    if suivis:
        requete_noms = text(
            "SELECT id::text AS id, (prenom || ' ' || nom) AS gestionnaire "
            "FROM core.utilisateur WHERE id::text IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        noms = (
            (await session.execute(requete_noms, {"ids": list(suivis)})).mappings().all()
        )
        evaluations.extend(
            {
                "id": n["id"],
                "gestionnaire": n["gestionnaire"],
                "volume": 0,
                "charge": 0,
                "resolus": 0,
                "mttr_jours": None,
                "prise_en_charge_h": None,
                "suivis": suivis[n["id"]],
            }
            for n in noms
        )
    return evaluations


@routeur.get("/gestionnaire/{ident}", response_model=GestionnaireDetail)
async def gestionnaire_detail(
    ident: str,
    courant: Courant,
    session: Session,
    jours: Annotated[int | None, Query(ge=1, le=3650)] = None,
    du: date | None = None,
    au: date | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"id": ident, **_pparams(jours, du, au)}
    requete = (
        f"SELECT (s.prenom || ' ' || s.nom) AS gestionnaire, {_AGREGATS_GEST} "
        f"FROM ({_src_gest(_periode(jours, du, au) + ' AND r.id::text = :id')}) s "
        "GROUP BY s.prenom, s.nom"
    )
    ligne = (await session.execute(text(requete), params)).mappings().first()
    activite = await _lignes(
        session,
        "SELECT extract(isodow from a.cree_le)::int AS jour, "
        "extract(hour from a.cree_le)::int AS heure, count(*) AS valeur "
        "FROM core.activite a WHERE a.responsable_id = cast(:id as uuid) "
        f"AND a.cree_le IS NOT NULL{_periode(jours, du, au)} GROUP BY 1, 2",
        params,
    )
    nb_suivis = (
        await session.scalar(
            text(
                "SELECT count(*) FROM core.activite_acteur aa "
                "JOIN core.activite a ON a.id = aa.activite_id "
                "WHERE aa.role = 'CONTRIBUTEUR' AND aa.utilisateur_id = cast(:id as uuid)"
                + _periode(jours, du, au)
            ),
            params,
        )
        or 0
    )
    if ligne is None:
        nom = await session.scalar(
            text("SELECT (prenom || ' ' || nom) FROM core.utilisateur WHERE id::text = :id"),
            {"id": ident},
        )
        return {
            "id": ident,
            "gestionnaire": nom or "—",
            "volume": 0,
            "charge": 0,
            "resolus": 0,
            "mttr_jours": None,
            "prise_en_charge_h": None,
            "suivis": nb_suivis,
            "activite": activite,
        }
    return {**_eval_dict({**ligne, "id": ident}), "suivis": nb_suivis, "activite": activite}


# --- Répartition mensuelle (tableaux croisés par mois) -------------------------------------------
# Granularité (jour/mois/année) partagée avec le dashboard : cf. application.granularite_temps.

# Volumétrie par priorité et respect SLA, par bucket de temps. TTR = durée réelle importée ; la
# cible vient de la règle SLA du module/priorité. `population` = tickets à durée mesurable.
_MENSUEL_PRIORITE = """
SELECT to_char(date_trunc('{trunc}', a.cree_le), '{fmt}') AS bucket, a.priorite AS niveau,
       count(*) AS total,
       count(*) FILTER (WHERE {ttr} > 0) AS population,
       count(*) FILTER (WHERE {ttr} > 0 AND {ttr} <= {cible}) AS dans_delai
FROM core.activite a
JOIN core.sla_regle sr ON sr.priorite = a.priorite AND sr.module = a.module
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.source = 'IMPORT_SD' AND a.priorite IS NOT NULL
  AND a.cree_le >= :b_debut AND a.cree_le < :b_fin{cond}
GROUP BY 1, 2
"""

# Répartition DSI (compte rattaché) / DBS (gestionnaire externe) / non renseigné, par bucket.
_MENSUEL_ENTITE = f"""
SELECT to_char(date_trunc('{{trunc}}', a.cree_le), '{{fmt}}') AS bucket,
       {_ENTITE_SQL} AS entite,
       count(*) AS total,
       count(*) FILTER (WHERE a.cloture_le IS NOT NULL) AS fermes,
       count(*) FILTER (
         WHERE a.cloture_le IS NULL AND a.statut NOT IN ('Rejeté','Rejetée')
       ) AS ouverts,
       count(*) FILTER (WHERE a.statut IN ('Rejeté','Rejetée')) AS rejetes,
       count(*) FILTER (WHERE a.module = 'incident') AS incidents,
       count(*) FILTER (WHERE a.module = 'demande') AS demandes
FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.source = 'IMPORT_SD'
  AND a.cree_le >= :b_debut AND a.cree_le < :b_fin{{cond}}
GROUP BY 1, 2
"""

# Répartition PAR GESTIONNAIRE, par bucket. Le gestionnaire est le compte DSI responsable, sinon
# le nom porté par le ticket importé ; sans nom renseigné, le ticket n'est chez personne.
_MENSUEL_NIVEAU = f"""
SELECT to_char(date_trunc('{{trunc}}', a.cree_le), '{{fmt}}') AS bucket,
       coalesce(nullif(u.prenom || ' ' || u.nom, ' '),
                nullif(trim(a.donnees->>'gestionnaire'), ''), 'Non renseigné') AS gestionnaire,
       CASE WHEN {_EST_DBS} THEN 'DBS'
            WHEN a.responsable_id IS NULL THEN 'NR'
            WHEN u.niveau_support = 1 THEN 'N1'
            WHEN u.niveau_support = 2 THEN 'N2'
            ELSE 'Autre' END AS niveau,
       count(*) AS total,
       count(*) FILTER (WHERE a.cloture_le IS NOT NULL) AS fermes,
       count(*) FILTER (
         WHERE a.cloture_le IS NULL AND a.statut NOT IN ('Rejeté','Rejetée')
       ) AS ouverts,
       count(*) FILTER (WHERE a.module = 'incident') AS incidents,
       count(*) FILTER (WHERE a.module = 'demande') AS demandes
FROM core.activite a
LEFT JOIN core.utilisateur u ON u.id = a.responsable_id
LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.source = 'IMPORT_SD' AND a.module IN ('incident','demande')
  AND a.cree_le >= :b_debut AND a.cree_le < :b_fin{{cond}}
GROUP BY 1, 2, 3
"""

# Familles d'état d'un ticket (le filtre de la synthèse) : ouvert / fermé / rejeté.
_STATUT_BUCKET = {
    "ouvert": " AND a.cloture_le IS NULL AND a.statut NOT IN ('Rejeté','Rejetée')",
    "ferme": " AND a.cloture_le IS NOT NULL",
    "rejete": " AND a.statut IN ('Rejeté','Rejetée')",
}

_PLAGE_IMPORT = """
SELECT min(a.cree_le) AS mini, max(a.cree_le) AS maxi
FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.source = 'IMPORT_SD'{cond}
"""


@routeur.get("/mensuel", response_model=AnalysesMensuelles)
async def analyses_mensuelles(
    courant: Courant,
    session: Session,
    jours: Annotated[int | None, Query(ge=1, le=3650)] = None,
    du: date | None = None,
    au: date | None = None,
    statut: Annotated[str | None, Query(max_length=60)] = None,
) -> dict[str, Any]:
    """Tableaux croisés dont l'axe de temps suit le filtre (jour → mois → année).

    ``statut`` : ``ouvert`` | ``ferme`` | ``rejete`` — restreint les agrégats à cet état (l'axe de
    temps ne bouge pas). Ce sont les trois familles d'état d'un ticket, pas des statuts bruts.
    """
    cond_dir = ""
    pdir: dict[str, Any] = {}
    if not courant["transverse"]:
        cond_dir = " AND (d.code = :dir OR a.direction_id IS NULL)"
        pdir["dir"] = courant["direction"]
    # Filtre statut : appliqué aux agrégats seulement (pas à la plage, pour garder le même axe).
    cond_agg = cond_dir + _STATUT_BUCKET.get(statut or "", "")

    maintenant = datetime.now(UTC)
    if du is not None or au is not None:
        debut = datetime(du.year, du.month, du.day, tzinfo=UTC) if du else maintenant
        fin = datetime(au.year, au.month, au.day, tzinfo=UTC) if au else maintenant
    elif jours is not None:
        debut, fin = maintenant - timedelta(days=jours), maintenant
    else:
        # « Tout » : on cadre sur l'étendue réelle des données importées (repli 12 mois si vide).
        bornes = (await session.execute(text(_PLAGE_IMPORT.format(cond=cond_dir)), pdir)).first()
        mini = bornes.mini if bornes is not None else None
        maxi = bornes.maxi if bornes is not None else None
        debut = mini or (maintenant - timedelta(days=365))
        fin = maxi or maintenant

    unit = _granularite(max(0, (fin - debut).days))
    trunc, fmt = _UNIT_SQL[unit], _FMT_SQL[unit]
    depart, dernier = _tronquer(unit, debut), _tronquer(unit, fin)
    buckets: list[datetime] = []
    courant_b = depart
    while courant_b <= dernier and len(buckets) < 400:
        buckets.append(courant_b)
        courant_b = _ajouter(unit, courant_b)
    if not buckets:
        buckets = [depart]

    params: dict[str, Any] = {"b_debut": buckets[0], "b_fin": _ajouter(unit, buckets[-1]), **pdir}
    entetes = [{"cle": _cle_bucket(unit, b), "libelle": _libelle_bucket(unit, b)} for b in buckets]
    cles = [e["cle"] for e in entetes]

    # Cible SLA par priorité (pour l'infobulle « P1 (SLA: 4h) »), module incident par défaut.
    cibles = {
        r["priorite"]: r["resolution_minutes"]
        for r in await _lignes(
            session,
            "SELECT priorite, min(resolution_minutes) AS resolution_minutes "
            "FROM core.sla_regle GROUP BY priorite",
            {},
        )
    }

    def _cell_sla(total: int, pop: int, ok: int, cle: str) -> dict[str, Any]:
        return {
            "mois": cle,
            "total": total,
            "population_sla": pop,
            "sla_taux": round(ok * 100 / pop, 1) if pop else None,
        }

    # --- Priorités × bucket --- (+ accumulateurs pour la ligne d'en-tête « toutes priorités »)
    lignes_p = await _lignes(
        session,
        _MENSUEL_PRIORITE.format(trunc=trunc, fmt=fmt, ttr=_TTR, cible=_CIBLE, cond=cond_agg),
        params,
    )
    par = {(int(r["niveau"]), str(r["bucket"])): r for r in lignes_p}
    tot_mois: dict[str, int] = dict.fromkeys(cles, 0)
    pop_mois: dict[str, int] = dict.fromkeys(cles, 0)
    ok_mois: dict[str, int] = dict.fromkeys(cles, 0)
    priorites = []
    for niveau in (1, 2, 3, 4, 5):
        cellules = []
        for cle in cles:
            r = par.get((niveau, cle))
            total = int(r["total"]) if r else 0
            pop = int(r["population"]) if r else 0
            ok = int(r["dans_delai"]) if r else 0
            tot_mois[cle] += total
            pop_mois[cle] += pop
            ok_mois[cle] += ok
            cellules.append(_cell_sla(total, pop, ok, cle))
        priorites.append(
            {"priorite": niveau, "cible_minutes": cibles.get(niveau), "cellules": cellules}
        )
    total_p = [_cell_sla(tot_mois[c], pop_mois[c], ok_mois[c], c) for c in cles]

    # --- Entités (DSI / DBS) × bucket ---
    lignes_e = await _lignes(
        session, _MENSUEL_ENTITE.format(trunc=trunc, fmt=fmt, cond=cond_agg), params
    )
    par_e = {(str(r["entite"]), str(r["bucket"])): r for r in lignes_e}
    champs = ("total", "fermes", "ouverts", "rejetes", "incidents", "demandes")
    entites = []
    # « Non renseigné » : ni chez nous, ni chez DBS. Ligne affichée seulement si elle existe, pour
    # ne pas laisser une ligne vide en permanence quand les fichiers sont bien remplis.
    for cle_e, libelle in (("DSI", "DSI AFG"), ("DBS", "DBS"), ("NR", "Non renseigné")):
        cellules = []
        cumuls: dict[str, int] = dict.fromkeys(champs, 0)
        for cle in cles:
            r = par_e.get((cle_e, cle))
            vals = {ch: (int(r[ch]) if r else 0) for ch in champs}
            for ch in champs:
                cumuls[ch] += vals[ch]
            cellules.append({"mois": cle, **vals})
        if cle_e == "NR" and cumuls["total"] == 0:
            continue
        entites.append(
            {
                "cle": cle_e,
                "libelle": libelle,
                "total": cumuls["total"],
                "fermes": cumuls["fermes"],
                "ouverts": cumuls["ouverts"],
                "incidents": cumuls["incidents"],
                "demandes": cumuls["demandes"],
                "cellules": cellules,
            }
        )

    # --- Par gestionnaire × bucket --- (une ligne par gestionnaire, classée par volume décroissant)
    lignes_n = await _lignes(
        session, _MENSUEL_NIVEAU.format(trunc=trunc, fmt=fmt, cond=cond_agg), params
    )
    par_n = {(str(r["gestionnaire"]), str(r["bucket"])): r for r in lignes_n}
    champs_n = ("total", "fermes", "ouverts", "incidents", "demandes")
    totaux_g: dict[str, int] = {}
    niveau_g: dict[str, str] = {}
    for r in lignes_n:
        g = str(r["gestionnaire"])
        totaux_g[g] = totaux_g.get(g, 0) + int(r["total"])
        niveau_g[g] = str(r["niveau"])
    # Nom en second critère : ordre stable quand deux gestionnaires ont le même volume.
    noms_g = sorted(totaux_g, key=lambda n: (-totaux_g[n], n))
    niveaux = []
    for nom in noms_g:
        cellules = []
        cumuls_n: dict[str, int] = dict.fromkeys(champs_n, 0)
        for cle in cles:
            r = par_n.get((nom, cle))
            vals = {ch: (int(r[ch]) if r else 0) for ch in champs_n}
            for ch in champs_n:
                cumuls_n[ch] += vals[ch]
            cellules.append({"mois": cle, **vals})
        niveaux.append(
            {
                "cle": nom,
                "libelle": nom,
                "niveau": niveau_g.get(nom, "Autre"),
                "total": cumuls_n["total"],
                "fermes": cumuls_n["fermes"],
                "ouverts": cumuls_n["ouverts"],
                "incidents": cumuls_n["incidents"],
                "demandes": cumuls_n["demandes"],
                "cellules": cellules,
            }
        )

    return {
        "granularite": unit,
        "mois": entetes,
        "total_priorites": total_p,
        "priorites": priorites,
        "entites": entites,
        "niveaux": niveaux,
    }

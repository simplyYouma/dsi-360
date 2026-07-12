"""Analyse / Reporting (cahier §8) : agrégations transverses (cloisonnées par direction).

Vise un vrai tableau analytique : KPI de pilotage (respect SLA, délai moyen de résolution,
retards), répartitions (module, priorité, direction, charge), matrice des risques
(probabilité × impact) et tendance hebdomadaire création vs résolution.
"""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import AnalysesReponse, GestionnaireDetail, GestionnaireEval
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

# DSI vs DBS (tickets importés) : sans responsable chez nous = chez DBS (ADR-0005).
_DBS = """
SELECT count(*) FILTER (WHERE a.responsable_id IS NOT NULL) AS dsi,
       count(*) FILTER (WHERE a.responsable_id IS NULL) AS dbs,
       count(*) FILTER (WHERE a.responsable_id IS NULL AND a.cloture_le IS NULL) AS dbs_ouverts,
       round((avg(extract(epoch FROM now() - a.cree_le) / 86400)
         FILTER (WHERE a.responsable_id IS NULL AND a.cloture_le IS NULL))::numeric, 1)
         AS dbs_age_jours
FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id
WHERE a.source = 'IMPORT_SD'{cond}
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
        cond_dir = " AND d.code = :dir"
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

    # La tendance suit la période : semaines couvrant la fenêtre choisie ; à défaut, 8 dernières.
    if du is not None or au is not None:
        borne_debut = (
            "date_trunc('week', cast(:du as date))"
            if du is not None
            else "date_trunc('week', now()) - interval '7 weeks'"
        )
        borne_fin = (
            "date_trunc('week', cast(:au as date))"
            if au is not None
            else "date_trunc('week', now())"
        )
    elif jours is not None:
        borne_debut = "date_trunc('week', now() - make_interval(days => :jours))"
        borne_fin = "date_trunc('week', now())"
    else:
        borne_debut = "date_trunc('week', now()) - interval '7 weeks'"
        borne_fin = "date_trunc('week', now())"
    tendance = await _lignes(
        session,
        "WITH semaines AS ("
        f"  SELECT generate_series({borne_debut}, {borne_fin}, interval '1 week') AS debut) "
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
    "round(avg(s.trep) FILTER (WHERE s.trep > 0) / 60.0, 1) AS prise_en_charge_h"
)


def _src_gest(extra: str) -> str:
    return (
        "SELECT r.id::text AS id, r.prenom, r.nom, a.cloture_le, a.resolu_le, "
        "  nullif(a.donnees->>'ttr_minutes', '')::numeric AS ttr, "
        "  nullif(a.donnees->>'ttrespond_minutes', '')::numeric AS trep "
        "FROM core.activite a JOIN core.utilisateur r ON r.id = a.responsable_id "
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

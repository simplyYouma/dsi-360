"""File de travail de l'agent DSI connecté : tickets (incidents/demandes…) qui lui sont assignés.

Vue temps réel « je me connecte et je vois ce que je dois traiter », triée par priorité puis
échéance SLA. Les éléments clôturés en sont exclus.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.etats import etats_terminaux
from dsi360.domain.sla import statut_sla
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import tache as tache_repo
from dsi360.interface.schemas import MesStats, PageMesTaches, PageMesTickets
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/mes-tickets", tags=["mes-tickets"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]
_FENETRE = timedelta(hours=2)

_MODULES = "('incident','demande','changement','audit','cybersecurite','gouvernance')"
_MODULES_LISTE = ("incident", "demande", "changement", "audit", "cybersecurite", "gouvernance")
# « Terminé sans suite » : états sans transition possible (rejeté/annulé/réalisé/clôturé selon le
# module). Complète la clôture (cloture_le) pour sortir aussi les cartes mortes de la file active.
_TERMINAUX = sorted({etat for m in _MODULES_LISTE for etat in etats_terminaux(m)})

# Condition de segment de la file (liste blanche — jamais d'entrée utilisateur dans le SQL).
# Ma file : les activités dont je suis le gestionnaire, et celles où l'administrateur m'a désigné
# contributeur. Sur un incident ou une demande, c'est le seul moyen d'entrer dans la file : leur
# gestionnaire vient du rapport, et il peut être DBS (ADR-0005).
_A_MOI = (
    "(a.responsable_id = cast(:id as uuid) OR EXISTS ("
    " SELECT 1 FROM core.activite_acteur aa WHERE aa.activite_id = a.id"
    "   AND aa.utilisateur_id = cast(:id as uuid) AND aa.role = 'CONTRIBUTEUR'))"
)

_SEGMENTS: dict[str, str] = {
    "actifs": "a.cloture_le IS NULL AND a.statut NOT IN :term",
    "resolus": "a.cloture_le IS NULL AND a.resolu_le IS NOT NULL AND a.statut NOT IN :term",
    "termines": "(a.cloture_le IS NOT NULL OR a.statut IN :term)",
    "tout": "TRUE",
}


def _requete_liste(segment: str) -> Any:
    cond = _SEGMENTS.get(segment, _SEGMENTS["actifs"])
    sql = (
        "SELECT a.module, a.id::text AS id, a.reference, a.titre, a.statut, a.priorite, "
        "a.sla_resolution_le, a.cree_le, dem.nom_complet AS demandeur, "
        "(SELECT count(*) FROM core.commentaire cm "
        " WHERE cm.activite_id = a.id AND cm.tache_id IS NULL) AS nb_commentaires, "
        "(SELECT count(*) FROM core.commentaire cm "
        " WHERE cm.activite_id = a.id AND cm.tache_id IS NULL "
        "   AND cm.auteur_id IS DISTINCT FROM cast(:id as uuid) "
        "   AND NOT EXISTS (SELECT 1 FROM core.commentaire_vue v "
        "                   WHERE v.commentaire_id = cm.id "
        "                     AND v.utilisateur_id = cast(:id as uuid))) AS nb_non_vus "
        "FROM core.activite a LEFT JOIN core.demandeur dem ON dem.id = a.demandeur_externe_id "
        f"WHERE {_A_MOI} AND a.module IN {_MODULES} AND {cond} "
        "ORDER BY a.priorite NULLS LAST, a.sla_resolution_le NULLS LAST "
        "LIMIT :taille OFFSET :decalage"
    )
    requete = text(sql)
    if ":term" in cond:
        requete = requete.bindparams(bindparam("term", expanding=True))
    return requete


_TAILLE_PAGE = 15


def _requete_total(segment: str) -> Any:
    cond = _SEGMENTS.get(segment, _SEGMENTS["actifs"])
    requete = text(f"SELECT count(*) FROM core.activite a WHERE {_A_MOI} "
                   f"AND a.module IN {_MODULES} AND {cond}")
    if ":term" in cond:
        requete = requete.bindparams(bindparam("term", expanding=True))
    return requete


@routeur.get("", response_model=PageMesTickets)
async def mes_tickets(
    courant: Courant,
    session: Session,
    segment: Annotated[str, Query()] = "actifs",
    page: Annotated[int, Query(ge=1)] = 1,
) -> dict[str, Any]:
    if segment not in _SEGMENTS:
        segment = "actifs"
    params: dict[str, Any] = {"id": courant["id"]}
    if segment != "tout":
        params["term"] = _TERMINAUX
    total = await session.scalar(_requete_total(segment), params) or 0
    lignes = (
        await session.execute(
            _requete_liste(segment),
            {**params, "taille": _TAILLE_PAGE, "decalage": (page - 1) * _TAILLE_PAGE},
        )
    ).mappings().all()
    maintenant = datetime.now(UTC)
    elements: list[dict[str, Any]] = []
    for r in lignes:
        echeance = r["sla_resolution_le"]
        etat = statut_sla(echeance, maintenant, _FENETRE) if echeance is not None else "a_lheure"
        elements.append({**dict(r), "statut_sla": etat})
    return {"elements": elements, "total": total}


_OUVERTS = text(
    "SELECT a.module, a.priorite, a.statut, a.sla_resolution_le, a.cree_le FROM core.activite a "
    f"WHERE {_A_MOI} AND a.cloture_le IS NULL AND a.module IN {_MODULES} "
    "AND a.statut NOT IN :term"
).bindparams(bindparam("term", expanding=True))
_RESOLUS = text(
    "SELECT a.cree_le, a.resolu_le, a.sla_resolution_le FROM core.activite a "
    f"WHERE {_A_MOI} AND a.resolu_le IS NOT NULL AND a.module IN {_MODULES} "
    "AND a.resolu_le >= :depuis"
)


def _comptes(valeurs: list[Any]) -> list[dict[str, Any]]:
    """Compte par libellé, du plus fréquent au moins fréquent."""
    compte = Counter(str(v) for v in valeurs if v is not None)
    return [{"libelle": k, "valeur": n} for k, n in compte.most_common()]


@routeur.get("/taches", response_model=PageMesTaches)
async def mes_taches(
    courant: Courant,
    session: Session,
    inclure_terminees: Annotated[bool, Query()] = False,
    page: Annotated[int, Query(ge=1)] = 1,
) -> dict[str, Any]:
    """Les tâches assignées à l'agent connecté, à travers tous les projets et changements."""
    lignes = await tache_repo.lister_pour_utilisateur(
        session, courant["id"], inclure_terminees=inclure_terminees
    )
    debut = (page - 1) * _TAILLE_PAGE
    return {
        "elements": [dict(r) for r in lignes[debut : debut + _TAILLE_PAGE]],
        "total": len(lignes),
    }


@routeur.get("/stats", response_model=MesStats)
async def mes_stats(courant: Courant, session: Session) -> dict[str, Any]:
    maintenant = datetime.now(UTC)
    ouverts = (
        await session.execute(_OUVERTS, {"id": courant["id"], "term": _TERMINAUX})
    ).mappings().all()
    resolus = (
        await session.execute(
            _RESOLUS, {"id": courant["id"], "depuis": maintenant - timedelta(days=90)}
        )
    ).mappings().all()

    # --- File ouverte : SLA, ancienneté, répartitions ---
    sla = Counter({"a_lheure": 0, "approche": 0, "depasse": 0})
    plus_ancien = 0
    for r in ouverts:
        if r["sla_resolution_le"] is not None:
            sla[statut_sla(r["sla_resolution_le"], maintenant, _FENETRE)] += 1
        age = (maintenant - r["cree_le"]).days
        plus_ancien = max(plus_ancien, age)

    par_priorite = [
        {"libelle": f"P{n}", "valeur": sum(1 for r in ouverts if r["priorite"] == n)}
        for n in (1, 2, 3, 4, 5)
    ]

    # --- Résolus (90 j) : volumes, respect SLA, délai moyen, tendance 14 j ---
    resolus_7j = sum(1 for r in resolus if r["resolu_le"] >= maintenant - timedelta(days=7))
    resolus_30j = sum(1 for r in resolus if r["resolu_le"] >= maintenant - timedelta(days=30))

    avec_cible = [r for r in resolus if r["sla_resolution_le"] is not None]
    dans_delai = sum(1 for r in avec_cible if r["resolu_le"] <= r["sla_resolution_le"])
    respect_sla = round(100 * dans_delai / len(avec_cible)) if avec_cible else 0

    delais = [(r["resolu_le"] - r["cree_le"]).total_seconds() / 86400 for r in resolus]
    mttr_jours = round(sum(delais) / len(delais), 1) if delais else None

    par_jour: Counter[str] = Counter()
    for r in resolus:
        par_jour[r["resolu_le"].date().isoformat()] += 1
    tendance: list[dict[str, Any]] = []
    for i in range(13, -1, -1):
        jour = (maintenant - timedelta(days=i)).date()
        tendance.append(
            {"jour": jour.strftime("%d/%m"), "resolus": par_jour.get(jour.isoformat(), 0)}
        )

    return {
        "agent": {
            "nom": f"{courant['prenom']} {courant['nom']}".strip(),
            "profil": courant.get("profil_libelle") or courant["profil"],
            "direction": courant["direction"],
        },
        "ouverts": len(ouverts),
        "a_lheure": sla["a_lheure"],
        "approche": sla["approche"],
        "en_retard": sla["depasse"],
        "resolus_7j": resolus_7j,
        "resolus_30j": resolus_30j,
        "respect_sla": respect_sla,
        "mttr_jours": mttr_jours,
        "plus_ancien_jours": plus_ancien if ouverts else None,
        "par_priorite": par_priorite,
        "par_module": _comptes([r["module"] for r in ouverts]),
        "par_statut": _comptes([r["statut"] for r in ouverts]),
        "tendance": tendance,
    }

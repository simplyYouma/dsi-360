"""File de travail de l'agent DSI connecté : tickets (incidents/demandes…) qui lui sont assignés.

Vue temps réel « je me connecte et je vois ce que je dois traiter », triée par priorité puis
échéance SLA. Les éléments clôturés en sont exclus.
"""

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.config.acces import PROFIL_ADMIN
from dsi360.domain.etats import PHASES_FINIES, etats_terminaux, statuts_de_phase
from dsi360.domain.sla import statut_sla
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import tache as tache_repo
from dsi360.interface.schemas import MesStats, PageMesTaches, PageMesTickets
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/mes-tickets", tags=["mes-tickets"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]
_FENETRE = timedelta(hours=2)


async def _id_cible(session: AsyncSession, courant: dict[str, Any], agent: str | None) -> str:
    """File que l'on regarde : la sienne, ou celle d'un agent choisi (réservé à l'administrateur).

    Un admin n'a presque jamais de tickets ; il doit pouvoir consulter la file d'un gestionnaire
    — ses tickets, tâches et analyses — comme si c'était lui, en lecture. Personne d'autre ne
    peut viser un autre agent : chacun ne voit que sa propre file.
    """
    if agent is None or agent == courant["id"]:
        return str(courant["id"])
    if courant["profil"] != PROFIL_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Consulter la file d'un autre agent est réservé à l'administrateur.",
        )
    existe = await session.scalar(
        text("SELECT 1 FROM core.utilisateur WHERE id::text = :id AND actif"), {"id": agent}
    )
    if existe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent introuvable.")
    return agent


async def _resoudre(
    session: AsyncSession, courant: dict[str, Any], agent: str | None
) -> tuple[str, bool]:
    """(file à lire, vue globale ?). ``agent='tous'`` = toutes les files (admin uniquement).

    Un admin n'a presque pas de tickets ; il consulte la file d'un agent, ou la file de *tous*.
    """
    if agent == "tous":
        if courant["profil"] != PROFIL_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La vue globale (tous les agents) est réservée à l'administrateur.",
            )
        return str(courant["id"]), True
    return await _id_cible(session, courant, agent), False


async def _bloc_agent(
    session: AsyncSession, courant: dict[str, Any], cible: str
) -> dict[str, Any]:
    """Identité affichée dans les analyses : soi, ou l'agent dont on consulte la file."""
    if cible == str(courant["id"]):
        return {
            "nom": f"{courant['prenom']} {courant['nom']}".strip(),
            "profil": courant.get("profil_libelle") or courant["profil"],
            "direction": courant["direction"],
        }
    r = (
        await session.execute(
            text(
                "SELECT u.prenom, u.nom, p.libelle AS profil, d.code AS direction "
                "FROM core.utilisateur u JOIN core.profil p ON p.id = u.profil_id "
                "LEFT JOIN core.direction d ON d.id = u.direction_id "
                "WHERE u.id::text = :id"
            ),
            {"id": cible},
        )
    ).mappings().first()
    if r is None:
        return {"nom": "", "profil": "", "direction": None}
    return {
        "nom": f"{r['prenom']} {r['nom']}".strip(),
        "profil": r["profil"],
        "direction": r["direction"],
    }

_MODULES = "('incident','demande','changement','audit','cybersecurite','gouvernance')"
_MODULES_LISTE = ("incident", "demande", "changement", "audit", "cybersecurite", "gouvernance")
# « Terminé sans suite » : états sans transition possible (rejeté/annulé/réalisé/clôturé selon le
# module). Complète la clôture (cloture_le) pour sortir aussi les cartes mortes de la file active.
# Terminé = feuille du cycle de vie (clôturé, rejeté, annulé…).
_TERMINES = sorted({etat for m in _MODULES_LISTE for etat in etats_terminaux(m)})
# Réglé = ne réclame plus de travail, résolu compris (le statut tranche : un import peut
# poser « Résolue » sans jamais dater la résolution).
_REGLES = statuts_de_phase(*PHASES_FINIES)

# Condition de segment de la file (liste blanche — jamais d'entrée utilisateur dans le SQL).
# Ma file : les activités dont je suis le gestionnaire, et celles où l'administrateur m'a désigné
# contributeur. Sur un incident ou une demande, c'est le seul moyen d'entrer dans la file : leur
# gestionnaire vient du rapport, et il peut être DBS (ADR-0005).
# « Mes tickets » = ceux où je suis responsable, contributeur OU valideur : un valideur doit
# retrouver dans sa liste les activités qu'il a à approuver.
_A_MOI = (
    "(a.responsable_id = cast(:id as uuid) OR EXISTS ("
    " SELECT 1 FROM core.activite_acteur aa WHERE aa.activite_id = a.id"
    "   AND aa.utilisateur_id = cast(:id as uuid) AND aa.role IN ('CONTRIBUTEUR', 'VALIDEUR')))"
)

# Activités où ma décision de valideur est encore attendue (décision non posée, activité non close).
_A_VALIDER = (
    "EXISTS (SELECT 1 FROM core.activite_acteur aa WHERE aa.activite_id = a.id"
    "   AND aa.utilisateur_id = cast(:id as uuid) AND aa.role = 'VALIDEUR'"
    "   AND aa.decision IS NULL) AND a.cloture_le IS NULL"
)

_SEGMENTS: dict[str, str] = {
    # Actif = ni clôturé, ni résolu (par date ou par statut).
    "actifs": "a.cloture_le IS NULL AND a.resolu_le IS NULL AND a.statut NOT IN :regles",
    # À valider : ma décision de valideur est encore attendue.
    "a_valider": _A_VALIDER,
    # Résolu mais pas encore archivé : par date OU par statut, tant que non terminal.
    "resolus": "a.cloture_le IS NULL AND (a.resolu_le IS NOT NULL OR a.statut IN :regles) "
    "AND a.statut NOT IN :termines",
    # Terminé = feuille du cycle de vie, ou clôture datée.
    "termines": "(a.cloture_le IS NOT NULL OR a.statut IN :termines)",
    "tout": "TRUE",
}


def _lier(requete: Any, cond: str) -> Any:
    """Déclare en 'expanding' les seuls ensembles que la condition référence."""
    for nom in ("regles", "termines"):
        if f":{nom}" in cond:
            requete = requete.bindparams(bindparam(nom, expanding=True))
    return requete


def _clause_q(recherche: bool) -> str:
    """Filtre plein-texte simple : référence ou titre contient la requête (ILIKE :q)."""
    return " AND (a.reference ILIKE :q OR a.titre ILIKE :q)" if recherche else ""


def _base(tous: bool) -> str:
    """Restriction de périmètre : ma file (`_A_MOI`), ou toutes les activités (vue globale)."""
    return "TRUE" if tous else _A_MOI


def _requete_liste(segment: str, recherche: bool = False, tous: bool = False) -> Any:
    cond = _SEGMENTS.get(segment, _SEGMENTS["actifs"]) + _clause_q(recherche)
    sql = (
        "SELECT a.module, a.id::text AS id, a.reference, a.titre, a.statut, a.priorite, "
        "a.sla_resolution_le, a.cree_le, a.resolu_le, a.cloture_le, dem.nom_complet AS demandeur, "
        "(SELECT count(*) FROM core.commentaire cm "
        " WHERE cm.activite_id = a.id AND cm.tache_id IS NULL) AS nb_commentaires, "
        "(SELECT count(*) FROM core.commentaire cm "
        " WHERE cm.activite_id = a.id AND cm.tache_id IS NULL "
        "   AND cm.auteur_id IS DISTINCT FROM cast(:id as uuid) "
        "   AND NOT EXISTS (SELECT 1 FROM core.commentaire_vue v "
        "                   WHERE v.commentaire_id = cm.id "
        "                     AND v.utilisateur_id = cast(:id as uuid))) AS nb_non_vus "
        "FROM core.activite a LEFT JOIN core.demandeur dem ON dem.id = a.demandeur_externe_id "
        f"WHERE {_base(tous)} AND a.module IN {_MODULES} AND {cond} "
        "ORDER BY a.priorite NULLS LAST, a.sla_resolution_le NULLS LAST "
        "LIMIT :taille OFFSET :decalage"
    )
    return _lier(text(sql), cond)


_TAILLE_PAGE = 15


def _requete_total(segment: str, recherche: bool = False, tous: bool = False) -> Any:
    cond = _SEGMENTS.get(segment, _SEGMENTS["actifs"]) + _clause_q(recherche)
    requete = text(f"SELECT count(*) FROM core.activite a WHERE {_base(tous)} "
                   f"AND a.module IN {_MODULES} AND {cond}")
    return _lier(requete, cond)


@routeur.get("", response_model=PageMesTickets)
async def mes_tickets(
    courant: Courant,
    session: Session,
    segment: Annotated[str, Query()] = "actifs",
    page: Annotated[int, Query(ge=1)] = 1,
    q: Annotated[str | None, Query()] = None,
    agent: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    if segment not in _SEGMENTS:
        segment = "actifs"
    cible, tous = await _resoudre(session, courant, agent)
    recherche = bool(q and q.strip())
    params: dict[str, Any] = {"id": cible, "regles": _REGLES, "termines": _TERMINES}
    if recherche:
        params["q"] = f"%{q.strip()}%"  # type: ignore[union-attr]
    total = await session.scalar(_requete_total(segment, recherche, tous), params) or 0
    # Compteur du segment « À valider » (badge) — sur toute la liste, indépendant de la recherche.
    a_valider = await session.scalar(_requete_total("a_valider", tous=tous), params) or 0
    lignes = (
        await session.execute(
            _requete_liste(segment, recherche, tous),
            {**params, "taille": _TAILLE_PAGE, "decalage": (page - 1) * _TAILLE_PAGE},
        )
    ).mappings().all()
    maintenant = datetime.now(UTC)
    elements: list[dict[str, Any]] = []
    for r in lignes:
        echeance = r["sla_resolution_le"]
        # Compteur figé dès que le travail a cessé : on ne garde que le verdict à l'arrêt.
        arret = r["resolu_le"] or r["cloture_le"]
        if echeance is None:
            etat = "a_lheure"
        elif arret is not None:
            etat = "depasse" if arret >= echeance else "a_lheure"
        else:
            etat = statut_sla(echeance, maintenant, _FENETRE)
        elements.append({**dict(r), "statut_sla": etat, "sla_arrete": arret is not None})
    return {"elements": elements, "total": total, "a_valider": a_valider}


def _ouverts(tous: bool = False) -> Any:
    return text(
        "SELECT a.module, a.priorite, a.statut, a.sla_resolution_le, a.cree_le "
        f"FROM core.activite a WHERE {_base(tous)} AND a.cloture_le IS NULL "
        f"AND a.resolu_le IS NULL AND a.module IN {_MODULES} AND a.statut NOT IN :regles"
    ).bindparams(bindparam("regles", expanding=True))


def _resolus(tous: bool = False) -> Any:
    return text(
        "SELECT a.cree_le, a.resolu_le, a.sla_resolution_le FROM core.activite a "
        f"WHERE {_base(tous)} AND a.resolu_le IS NOT NULL AND a.module IN {_MODULES} "
        "AND a.resolu_le >= :depuis AND a.resolu_le < :jusqua"
    )


def _fenetre_periode(
    jours: int | None, du: date | None, au: date | None, maintenant: datetime
) -> tuple[datetime, datetime]:
    """Fenêtre [début, fin[ des résolutions. Dates explicites > jours > tout."""
    loin = datetime(1970, 1, 1, tzinfo=UTC)
    futur = maintenant + timedelta(days=1)
    if du is not None or au is not None:
        debut = datetime(du.year, du.month, du.day, tzinfo=UTC) if du is not None else loin
        fin = datetime(au.year, au.month, au.day, tzinfo=UTC) + timedelta(days=1) if au else futur
        return debut, fin
    if jours is not None:
        return maintenant - timedelta(days=jours), futur
    return loin, futur


def _tendance_resolus(
    resolus: list[Any], dernier: date, portee_jours: int
) -> list[dict[str, Any]]:
    """Rythme de résolution sur les `portee_jours` finissant à `dernier` (inclus) : quotidien si
    court, hebdomadaire au-delà — pour garder un nombre de points lisible."""
    pas = 7 if portee_jours > 31 else 1
    n = (portee_jours + pas - 1) // pas
    seaux: Counter[int] = Counter()
    for r in resolus:
        delta = (dernier - r["resolu_le"].date()).days
        if 0 <= delta < portee_jours:
            seaux[delta // pas] += 1
    points: list[dict[str, Any]] = []
    for i in range(n - 1, -1, -1):
        jour = dernier - timedelta(days=i * pas)
        points.append({"jour": jour.strftime("%d/%m"), "resolus": seaux.get(i, 0)})
    return points


def _comptes(valeurs: list[Any]) -> list[dict[str, Any]]:
    """Compte par libellé, du plus fréquent au moins fréquent."""
    compte = Counter(str(v) for v in valeurs if v is not None)
    return [{"libelle": k, "valeur": n} for k, n in compte.most_common()]


def _stats_taches(lignes: list[Any], aujourdhui: date) -> dict[str, int]:
    """Répartition des tâches actives : à faire, en cours, en retard (échéance dépassée)."""
    a_faire = sum(1 for r in lignes if r["statut"] == "À faire")
    en_cours = sum(1 for r in lignes if r["statut"] == "En cours")
    en_retard = sum(
        1
        for r in lignes
        if r["echeance"] is not None and r["echeance"] < aujourdhui and r["statut"] != "Terminée"
    )
    return {"a_faire": a_faire, "en_cours": en_cours, "en_retard": en_retard}


@routeur.get("/taches", response_model=PageMesTaches)
async def mes_taches(
    courant: Courant,
    session: Session,
    inclure_terminees: Annotated[bool, Query()] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    q: Annotated[str | None, Query()] = None,
    filtre: Annotated[str | None, Query()] = None,
    agent: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Les tâches assignées à l'agent connecté, à travers tous les projets et changements."""
    cible, tous = await _resoudre(session, courant, agent)
    aujourdhui = datetime.now(UTC).date()
    toutes = await tache_repo.lister_pour_utilisateur(
        session, cible, inclure_terminees=inclure_terminees, tous=tous
    )
    stats = _stats_taches(toutes, aujourdhui)  # compté sur TOUTES : les tuiles ne bougent pas.
    lignes = toutes
    # Filtre rapide (tuile cliquée) : à faire / en cours / en retard.
    if filtre == "a_faire":
        lignes = [r for r in lignes if r["statut"] == "À faire"]
    elif filtre == "en_cours":
        lignes = [r for r in lignes if r["statut"] == "En cours"]
    elif filtre == "en_retard":
        lignes = [
            r
            for r in lignes
            if r["echeance"] is not None
            and r["echeance"] < aujourdhui
            and r["statut"] != "Terminée"
        ]
    if q and q.strip():
        terme = q.strip().lower()
        lignes = [
            r
            for r in lignes
            if terme in (r["titre"] or "").lower()
            or terme in (r["reference"] or "").lower()
            or terme in (r["activite_titre"] or "").lower()
        ]
    debut = (page - 1) * _TAILLE_PAGE
    return {
        "elements": [dict(r) for r in lignes[debut : debut + _TAILLE_PAGE]],
        "total": len(lignes),
        "stats": stats,
    }


@routeur.get("/stats", response_model=MesStats)
async def mes_stats(
    courant: Courant,
    session: Session,
    jours: Annotated[int | None, Query(ge=1, le=3650)] = None,
    du: date | None = None,
    au: date | None = None,
    agent: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    cible, tous = await _resoudre(session, courant, agent)
    maintenant = datetime.now(UTC)
    debut, fin = _fenetre_periode(jours, du, au, maintenant)
    ouverts = (
        await session.execute(_ouverts(tous), {"id": cible, "regles": _REGLES})
    ).mappings().all()
    resolus = (
        await session.execute(_resolus(tous), {"id": cible, "depuis": debut, "jusqua": fin})
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

    # --- Résolus SUR LA PÉRIODE : volume, respect SLA, délai moyen, rythme ---
    resolus_periode = len(resolus)

    avec_cible = [r for r in resolus if r["sla_resolution_le"] is not None]
    dans_delai = sum(1 for r in avec_cible if r["resolu_le"] <= r["sla_resolution_le"])
    respect_sla = round(100 * dans_delai / len(avec_cible)) if avec_cible else 0

    delais = [(r["resolu_le"] - r["cree_le"]).total_seconds() / 86400 for r in resolus]
    mttr_jours = round(sum(delais) / len(delais), 1) if delais else None

    # Rythme : sur la période, borné à un an pour rester lisible. « Tout » → 12 dernières semaines.
    borne = jours is not None or du is not None or au is not None
    portee = min((fin - debut).days, 366) if borne else 84
    dernier = min((au if au is not None else maintenant.date()), maintenant.date())
    tendance = _tendance_resolus(list(resolus), dernier, max(7, portee))

    return {
        "agent": (
            {"nom": "Tous les agents", "profil": "Vue globale", "direction": None}
            if tous
            else await _bloc_agent(session, courant, cible)
        ),
        "ouverts": len(ouverts),
        "a_lheure": sla["a_lheure"],
        "approche": sla["approche"],
        "en_retard": sla["depasse"],
        "resolus_periode": resolus_periode,
        "respect_sla": respect_sla,
        "mttr_jours": mttr_jours,
        "plus_ancien_jours": plus_ancien if ouverts else None,
        "par_priorite": par_priorite,
        "par_module": _comptes([r["module"] for r in ouverts]),
        "par_statut": _comptes([r["statut"] for r in ouverts]),
        "tendance": tendance,
    }

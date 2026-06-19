"""File de travail de l'agent DSI connecté : tickets (incidents/demandes…) qui lui sont assignés.

Vue temps réel « je me connecte et je vois ce que je dois traiter », triée par priorité puis
échéance SLA. Les éléments clôturés en sont exclus.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.sla import statut_sla
from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import MesStats, MonTicket
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/mes-tickets", tags=["mes-tickets"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]
_FENETRE = timedelta(hours=2)

_REQUETE = text(
    "SELECT a.module, a.id::text AS id, a.reference, a.titre, a.statut, a.priorite, "
    "a.sla_resolution_le, a.cree_le, dem.nom_complet AS demandeur, "
    "(SELECT count(*) FROM core.commentaire cm WHERE cm.activite_id = a.id) AS nb_commentaires "
    "FROM core.activite a LEFT JOIN core.demandeur dem ON dem.id = a.demandeur_externe_id "
    "WHERE a.responsable_id = cast(:id as uuid) AND a.cloture_le IS NULL "
    "AND a.module IN ('incident','demande','changement','audit','cybersecurite','gouvernance') "
    "ORDER BY a.priorite NULLS LAST, a.sla_resolution_le NULLS LAST LIMIT 200"
)


@routeur.get("", response_model=list[MonTicket])
async def mes_tickets(courant: Courant, session: Session) -> list[dict[str, Any]]:
    lignes = (await session.execute(_REQUETE, {"id": courant["id"]})).mappings().all()
    maintenant = datetime.now(UTC)
    resultat: list[dict[str, Any]] = []
    for r in lignes:
        echeance = r["sla_resolution_le"]
        etat = statut_sla(echeance, maintenant, _FENETRE) if echeance is not None else "a_lheure"
        resultat.append({**dict(r), "statut_sla": etat})
    return resultat


_MODULES = "('incident','demande','changement','audit','cybersecurite','gouvernance')"
_OUVERTS = text(
    "SELECT module, priorite, statut, sla_resolution_le, cree_le FROM core.activite "
    f"WHERE responsable_id = cast(:id as uuid) AND cloture_le IS NULL AND module IN {_MODULES}"
)
_RESOLUS = text(
    "SELECT cree_le, resolu_le, sla_resolution_le FROM core.activite "
    f"WHERE responsable_id = cast(:id as uuid) AND resolu_le IS NOT NULL AND module IN {_MODULES} "
    "AND resolu_le >= :depuis"
)


def _comptes(valeurs: list[Any]) -> list[dict[str, Any]]:
    """Compte par libellé, du plus fréquent au moins fréquent."""
    compte = Counter(str(v) for v in valeurs if v is not None)
    return [{"libelle": k, "valeur": n} for k, n in compte.most_common()]


@routeur.get("/stats", response_model=MesStats)
async def mes_stats(courant: Courant, session: Session) -> dict[str, Any]:
    maintenant = datetime.now(UTC)
    ouverts = (await session.execute(_OUVERTS, {"id": courant["id"]})).mappings().all()
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

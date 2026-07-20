"""Référentiels en lecture (catégories par module…), pour alimenter les formulaires."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.etats import ETATS, ordre_etats
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import sla as repo_sla
from dsi360.interface.schemas import (
    AgentItem,
    CategorieItem,
    EtatReferentiel,
    SlaRegleItem,
)
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/referentiels", tags=["referentiels"])

_CATEGORIES = text(
    "SELECT id::text AS id, code, libelle FROM core.categorie "
    "WHERE module = :module ORDER BY libelle"
)

# Agents désignables. Avec `module` (clé d'accès, ex. « changements ») : seuls les comptes actifs
# dont le profil a cet accès — on ne désigne pas quelqu'un à qui l'écran resterait fermé.
# Sans `module` : tous les actifs, pour l'autocomplétion des mentions @.
#
# Le filtre passe par core.acces_role, jamais par une liste de codes de profils : ceux-ci se créent
# et se suppriment depuis l'administration (ADR-0003).
_AGENTS = text(
    "SELECT u.id::text AS id, (u.prenom || ' ' || u.nom) AS nom, p.code AS profil "
    "FROM core.utilisateur u JOIN core.profil p ON p.id = u.profil_id "
    "WHERE u.actif AND (cast(:module as text) IS NULL OR EXISTS ("
    "    SELECT 1 FROM core.acces_role ar "
    "    WHERE ar.profil_code = p.code AND ar.acces = :module)) "
    "ORDER BY u.prenom, u.nom"
)


@routeur.get("/categories", response_model=list[CategorieItem])
async def categories(
    module: Annotated[str, Query()],
    session: Annotated[AsyncSession, Depends(session_scope)],
    _: Annotated[dict[str, Any], Depends(utilisateur_courant)],
) -> list[dict[str, Any]]:
    resultat = await session.execute(_CATEGORIES, {"module": module})
    return [dict(ligne) for ligne in resultat.mappings().all()]


@routeur.get("/agents", response_model=list[AgentItem])
async def agents(
    session: Annotated[AsyncSession, Depends(session_scope)],
    _: Annotated[dict[str, Any], Depends(utilisateur_courant)],
    module: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    """Comptes désignables. `module` = clé d'accès (« incidents », « projets »…)."""
    resultat = await session.execute(_AGENTS, {"module": module})
    return [dict(ligne) for ligne in resultat.mappings().all()]


@routeur.get("/etats", response_model=list[str])
async def etats(
    module: Annotated[str, Query()],
    _: Annotated[dict[str, Any], Depends(utilisateur_courant)],
) -> list[str]:
    # Un module inconnu est une erreur du client (mauvaise clé), pas du serveur : 404, pas 500.
    try:
        return ordre_etats(module)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


# Renommage d'affichage : le sigle ITIL reste le statut stocké (base, historique, workflow), mais
# l'écran montre un libellé clair. Ici, en couche interface : c'est de la présentation.
_LIBELLE_STATUT = {
    "CAB": "Attente comité",
    "ECAB": "Validation express",
}


@routeur.get("/cycles-de-vie", response_model=dict[str, list[EtatReferentiel]])
async def cycles_de_vie(
    _: Annotated[dict[str, Any], Depends(utilisateur_courant)],
) -> dict[str, list[dict[str, str]]]:
    """Cycle de vie de chaque module : statuts ordonnés, avec leur phase et leur ton.

    Le front n'a plus à redeviner le sens d'un statut : il le lit ici. Une seule déclaration
    (`domain.etats`) alimente les filtres, les compteurs et les couleurs.
    """
    return {
        module: [
            {
                "cle": nom,
                "libelle": _LIBELLE_STATUT.get(nom, nom),
                "phase": etat.phase,
                "ton": etat.ton,
            }
            for nom, etat in cycle.items()
        ]
        for module, cycle in ETATS.items()
    }


@routeur.get("/sla", response_model=list[SlaRegleItem])
async def sla(
    session: Annotated[AsyncSession, Depends(session_scope)],
    _: Annotated[dict[str, Any], Depends(utilisateur_courant)],
    module: Annotated[str, Query()],
) -> list[dict[str, Any]]:
    """Cibles SLA effectives d'un module (règles propres, sinon valeurs par défaut) — aperçu."""
    return await repo_sla.lister(session, module)

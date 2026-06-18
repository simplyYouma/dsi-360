"""Référentiels en lecture (catégories par module…), pour alimenter les formulaires."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.etats import ordre_etats
from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import AgentItem, CategorieItem
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/referentiels", tags=["referentiels"])

_CATEGORIES = text(
    "SELECT id::text AS id, code, libelle FROM core.categorie "
    "WHERE module = :module ORDER BY libelle"
)

# Agents DSI assignables (gestionnaires de tickets).
_AGENTS = text(
    "SELECT u.id::text AS id, (u.prenom || ' ' || u.nom) AS nom, p.code AS profil "
    "FROM core.utilisateur u JOIN core.profil p ON p.id = u.profil_id "
    "WHERE u.actif AND p.code IN "
    "('ADMIN','DSI','CHEF_SERVICE','CHEF_PROJET','TECHNICIEN') "
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
) -> list[dict[str, Any]]:
    resultat = await session.execute(_AGENTS)
    return [dict(ligne) for ligne in resultat.mappings().all()]


@routeur.get("/etats", response_model=list[str])
async def etats(
    module: Annotated[str, Query()],
    _: Annotated[dict[str, Any], Depends(utilisateur_courant)],
) -> list[str]:
    return ordre_etats(module)

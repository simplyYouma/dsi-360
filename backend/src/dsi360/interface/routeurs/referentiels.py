"""Référentiels en lecture (catégories par module…), pour alimenter les formulaires."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import CategorieItem
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/referentiels", tags=["referentiels"])

_CATEGORIES = text(
    "SELECT id::text AS id, code, libelle FROM core.categorie "
    "WHERE module = :module ORDER BY libelle"
)


@routeur.get("/categories", response_model=list[CategorieItem])
async def categories(
    module: Annotated[str, Query()],
    session: Annotated[AsyncSession, Depends(session_scope)],
    _: Annotated[dict[str, Any], Depends(utilisateur_courant)],
) -> list[dict[str, Any]]:
    resultat = await session.execute(_CATEGORIES, {"module": module})
    return [dict(ligne) for ligne in resultat.mappings().all()]

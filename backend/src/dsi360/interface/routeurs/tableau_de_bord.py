"""Tableau de bord : indicateurs agrégés (cloisonnés par direction). RBAC tableau-de-bord."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.indicateurs import tableau_de_bord
from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import TableauBord
from dsi360.interface.securite import exiger_acces

routeur = APIRouter(prefix="/tableau-de-bord", tags=["tableau-de-bord"])

Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces("tableau-de-bord"))]


@routeur.get("", response_model=TableauBord)
async def indicateurs(courant: Courant, session: Session) -> dict[str, Any]:
    direction = None if courant["transverse"] else courant["direction"]
    return await tableau_de_bord(session, direction)

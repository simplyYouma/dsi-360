"""Notifications personnelles de l'utilisateur connecté (cloche)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import NotificationsReponse
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/notifications", tags=["notifications"])

Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]

_LISTE = text(
    "SELECT id, type, titre, message, lu, cree_le FROM core.notification "
    "WHERE destinataire_id = cast(:id as uuid) ORDER BY id DESC LIMIT 30"
)
_NON_LUS = text(
    "SELECT count(*) FROM core.notification "
    "WHERE destinataire_id = cast(:id as uuid) AND lu = false"
)
_TOUT_LU = text(
    "UPDATE core.notification SET lu = true "
    "WHERE destinataire_id = cast(:id as uuid) AND lu = false"
)


@routeur.get("", response_model=NotificationsReponse)
async def lister(courant: Courant, session: Session) -> dict[str, Any]:
    lignes = (await session.execute(_LISTE, {"id": courant["id"]})).mappings().all()
    non_lus = await session.scalar(_NON_LUS, {"id": courant["id"]}) or 0
    return {"elements": [dict(x) for x in lignes], "non_lus": non_lus}


@routeur.post("/tout-lu", status_code=status.HTTP_204_NO_CONTENT)
async def tout_marquer_lu(courant: Courant, session: Session) -> None:
    await session.execute(_TOUT_LU, {"id": courant["id"]})
    await session.commit()

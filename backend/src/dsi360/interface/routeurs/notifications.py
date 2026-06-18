"""Notifications personnelles de l'utilisateur connecté (cloche)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import NotificationsReponse, PreferencesNotif
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/notifications", tags=["notifications"])

Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]

_LISTE = text(
    "SELECT n.id, n.type, n.titre, n.message, n.lu, n.cree_le, "
    "a.module AS module, a.id::text AS activite_id "
    "FROM core.notification n "
    "LEFT JOIN core.activite a ON a.id = n.activite_id "
    "WHERE n.destinataire_id = cast(:id as uuid) ORDER BY n.id DESC LIMIT 30"
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


_PREF = text(
    "SELECT interne, email, teams, whatsapp FROM core.preference_notification "
    "WHERE utilisateur_id = cast(:id as uuid)"
)
_PREF_UPSERT = text(
    "INSERT INTO core.preference_notification(utilisateur_id, interne, email, teams, whatsapp) "
    "VALUES (cast(:id as uuid), :interne, :email, :teams, :whatsapp) "
    "ON CONFLICT (utilisateur_id) DO UPDATE SET "
    "interne = excluded.interne, email = excluded.email, "
    "teams = excluded.teams, whatsapp = excluded.whatsapp"
)


@routeur.get("/preferences", response_model=PreferencesNotif)
async def preferences(courant: Courant, session: Session) -> dict[str, Any]:
    ligne = (await session.execute(_PREF, {"id": courant["id"]})).mappings().first()
    if ligne is None:
        return {"interne": True, "email": True, "teams": False, "whatsapp": False}
    return dict(ligne)


@routeur.put("/preferences", status_code=status.HTTP_204_NO_CONTENT)
async def definir_preferences(corps: PreferencesNotif, courant: Courant, session: Session) -> None:
    await session.execute(
        _PREF_UPSERT,
        {
            "id": courant["id"],
            "interne": corps.interne,
            "email": corps.email,
            "teams": corps.teams,
            "whatsapp": corps.whatsapp,
        },
    )
    await session.commit()

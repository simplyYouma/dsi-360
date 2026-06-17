"""Dépendances de sécurité de l'API : utilisateur courant (Bearer JWT) et gardes RBAC."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.auth import profil_complet
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import utilisateur as repo
from dsi360.infrastructure.securite import decoder_jeton

_bearer = HTTPBearer(auto_error=False)

_NON_AUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentification requise ou invalide.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def utilisateur_courant(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(session_scope)],
) -> dict[str, Any]:
    if creds is None:
        raise _NON_AUTH
    try:
        charge = decoder_jeton(creds.credentials)
    except jwt.PyJWTError as exc:
        raise _NON_AUTH from exc
    if charge.get("type") != "acces":
        raise _NON_AUTH
    u = await repo.par_id(session, str(charge.get("sub")))
    if u is None or not u["actif"]:
        raise _NON_AUTH
    return await profil_complet(session, u)


UtilisateurCourant = Annotated[dict[str, Any], Depends(utilisateur_courant)]


def exiger_acces(*cles: str) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Garde : l'utilisateur doit avoir l'un des accès demandés."""

    async def _verifier(courant: UtilisateurCourant) -> dict[str, Any]:
        if not any(cle in courant["acces"] for cle in cles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé pour ce profil.",
            )
        return courant

    return _verifier

"""Dépendances de sécurité de l'API : utilisateur courant (Bearer JWT) et gardes RBAC.

Deux niveaux de garde, à ne pas confondre :

- ``exiger_acces(module)`` : l'utilisateur a-t-il accès à cette **page** ? (matrice ``acces_role``)
- ``exiger_role_activite(...)`` : a-t-il le **rôle** requis sur *cette* activité ? (responsable,
  contributeur, valideur…) Cf. ``application.autorisations``.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.auth import compte_actif, profil_complet
from dsi360.application.autorisations import (
    RolesActivite,
    charger_roles,
    satisfait,
    visible,
)
from dsi360.config.acces import PROFIL_ADMIN
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import activite as repo_activite
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
    if u is None or not compte_actif(u):
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


def exiger_admin(courant: dict[str, Any]) -> None:
    """Garde impérative, pour une route qui ne porte pas sur une activité (assignation en lot)."""
    if courant["profil"] != PROFIL_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action réservée à l'administrateur.",
        )


@dataclass(frozen=True)
class ContexteActivite:
    """Activité chargée, rôles de l'appelant, et l'appelant. Évite de relire l'activité en route."""

    activite: RowMapping
    roles: RolesActivite
    courant: dict[str, Any]


def exiger_role_activite(
    module: str, acces: str, requis: set[str] | None = None
) -> Callable[..., Awaitable[ContexteActivite]]:
    """Garde : accès au module, puis périmètre, puis rôle sur cette activité.

    ``requis`` vide (ou ``None``) = simple lecture : il suffit de voir l'activité.
    Hors périmètre → 404 : une activité qu'on n'a pas le droit de voir n'existe pas pour nous.
    """
    attendus = requis or set()

    async def _verifier(
        ident: str,
        courant: Annotated[dict[str, Any], Depends(exiger_acces(acces))],
        session: Annotated[AsyncSession, Depends(session_scope)],
    ) -> ContexteActivite:
        r = await repo_activite.par_id(session, module, ident, moi=courant["id"])
        if r is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Introuvable.")
        roles = await charger_roles(session, r, courant)
        if not visible(r["direction"], courant, roles):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Introuvable.")
        if attendus and not satisfait(roles, attendus):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Action non autorisée pour votre rôle sur cette activité.",
            )
        return ContexteActivite(activite=r, roles=roles, courant=courant)

    return _verifier

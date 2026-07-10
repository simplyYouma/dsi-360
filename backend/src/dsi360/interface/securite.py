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
    AgentIneligible,
    RolesActivite,
    charger_roles,
    controler_champs_tache,
    exiger_designable,
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


async def exiger_agent_designable(
    session: AsyncSession, utilisateur_id: str | None, acces: str
) -> None:
    """Traduit la règle de désignation en réponse HTTP. ``None`` = désassignation, permise."""
    if utilisateur_id is None:
        return
    try:
        await exiger_designable(session, utilisateur_id, acces)
    except AgentIneligible as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


def exiger_champs_tache(
    roles: RolesActivite,
    tache: RowMapping,
    courant: dict[str, Any],
    champs: dict[str, Any],
) -> None:
    """Traduit en 403 le contrôle champ par champ d'une tâche (cf. `controler_champs_tache`)."""
    assigne = tache["assigne_id"] is not None and str(tache["assigne_id"]) == courant["id"]
    motif = controler_champs_tache(roles, assigne_de_la_tache=assigne, champs=champs)
    if motif is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=motif)


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


def exiger_role_activite_courant(
    module: str, acces: str, requis: set[str] | None = None
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Même garde, mais renvoie l'utilisateur courant.

    Les registrars (documents, liens, tâches) attendent une dépendance ``Courant`` : on leur en
    fournit une qui vérifie en plus le rôle sur l'activité, sans changer leur signature.
    """
    garde = exiger_role_activite(module, acces, requis)

    async def _verifier(ctx: Annotated[ContexteActivite, Depends(garde)]) -> dict[str, Any]:
        return ctx.courant

    return _verifier

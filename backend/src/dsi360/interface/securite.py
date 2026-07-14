"""Dépendances de sécurité de l'API : utilisateur courant (Bearer JWT) et gardes RBAC.

Deux niveaux de garde, à ne pas confondre :

- ``exiger_acces(module)`` : l'utilisateur a-t-il accès à cette **page** ? (matrice ``acces_role``)
- ``exiger_role_activite(...)`` : a-t-il le **rôle** requis sur *cette* activité ? (responsable,
  contributeur, valideur…) Cf. ``application.autorisations``.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, Final

import jwt
from fastapi import Depends, HTTPException, Request, status
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
from dsi360.domain.etats import est_etat_terminal
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

# Seules routes joignables tant que le mot de passe n'a pas été renouvelé : lire son propre profil
# (l'écran doit pouvoir savoir qu'il doit rediriger), changer son mot de passe, et se déconnecter.
_CHEMINS_SANS_MDP_A_JOUR: Final = ("/moi", "/auth/mot-de-passe", "/auth/logout")


async def utilisateur_courant(
    requete: Request,
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
    incarne_par = charge.get("incarne_par")
    # Mot de passe à renouveler (compte semé, ou créé/réinitialisé par l'administrateur) : le
    # serveur ferme l'application, il ne se contente pas d'une redirection à l'écran. Sinon le
    # mot de passe initial — celui du `.env`, connu de l'exploitant — resterait un accès complet
    # et permanent à l'API, hors de tout écran. Contrôle côté serveur : incontournable.
    #
    # Exception : l'incarnation (dev). Regarder les écrans d'un agent qui n'a pas encore renouvelé
    # son mot de passe doit rester possible — l'écran ne redirige pas non plus dans ce cas.
    if (
        u["doit_changer_mdp"]
        and incarne_par is None
        and not requete.url.path.endswith(_CHEMINS_SANS_MDP_A_JOUR)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Renouvelez votre mot de passe avant d'utiliser l'application.",
        )
    return {
        **await profil_complet(session, u),
        "incarne_par": str(incarne_par) if incarne_par else None,
    }


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
    module: str, acces: str, requis: set[str] | None = None, *, bloquer_si_clos: bool = False
) -> Callable[..., Awaitable[ContexteActivite]]:
    """Garde : accès au module, puis périmètre, puis rôle sur cette activité.

    ``requis`` vide (ou ``None``) = simple lecture : il suffit de voir l'activité.
    Hors périmètre → 404 : une activité qu'on n'a pas le droit de voir n'existe pas pour nous.

    ``bloquer_si_clos`` : refuse (409) toute mutation d'une activité dans un état terminal. À poser
    sur les routes de modification du contenu ; laissé à ``False`` pour le dossier (RFC, liens) et
    la discussion, qui restent ouverts après clôture.
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
        if bloquer_si_clos and est_etat_terminal(module, r["statut"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Activité clôturée : lecture seule. Seuls la discussion, les analyses/plans "
                    "(RFC) et les liens restent ouverts."
                ),
            )
        return ContexteActivite(activite=r, roles=roles, courant=courant)

    return _verifier


def exiger_role_activite_courant(
    module: str, acces: str, requis: set[str] | None = None, *, bloquer_si_clos: bool = False
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Même garde, mais renvoie l'utilisateur courant.

    Les registrars (documents, liens, tâches) attendent une dépendance ``Courant`` : on leur en
    fournit une qui vérifie en plus le rôle sur l'activité, sans changer leur signature.
    """
    garde = exiger_role_activite(module, acces, requis, bloquer_si_clos=bloquer_si_clos)

    async def _verifier(ctx: Annotated[ContexteActivite, Depends(garde)]) -> dict[str, Any]:
        return ctx.courant

    return _verifier

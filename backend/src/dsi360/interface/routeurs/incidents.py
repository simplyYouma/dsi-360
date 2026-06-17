"""Module Incidents : liste, création, détail, transition. RBAC + cloisonnement + audit."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.activites import (
    ActiviteIntrouvable,
    TransitionInterdite,
    creer_activite,
    transition,
)
from dsi360.domain.etats import transitions_possibles
from dsi360.domain.sla import statut_sla
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import activite as repo
from dsi360.interface.schemas import (
    ActiviteCreation,
    ActiviteDetail,
    CreationReponse,
    PageActivites,
    TransitionDemande,
)
from dsi360.interface.securite import exiger_acces

MODULE = "incident"  # module domaine (table core.activite)
_ACCES = "incidents"  # clé d'accès RBAC (catalogue / navigation)
_TAILLE = 15
_FENETRE_APPROCHE = timedelta(hours=2)

routeur = APIRouter(prefix="/incidents", tags=["incidents"])

Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces(_ACCES))]


def _statut_sla(resolution_le: datetime | None, maintenant: datetime) -> str:
    if resolution_le is None:
        return "a_lheure"
    return statut_sla(resolution_le, maintenant, _FENETRE_APPROCHE)


def _responsable(r: RowMapping) -> dict[str, str] | None:
    if r["resp_email"] is None:
        return None
    return {"prenom": r["resp_prenom"], "nom": r["resp_nom"], "email": r["resp_email"]}


def _resume(r: RowMapping, maintenant: datetime) -> dict[str, Any]:
    return {
        "id": r["id"],
        "reference": r["reference"],
        "titre": r["titre"],
        "statut": r["statut"],
        "priorite": r["priorite"],
        "categorie": r["categorie"],
        "direction": r["direction"],
        "sla_resolution_le": r["sla_resolution_le"],
        "statut_sla": _statut_sla(r["sla_resolution_le"], maintenant),
        "cree_le": r["cree_le"],
        "responsable": _responsable(r),
    }


def _detail(r: RowMapping, maintenant: datetime) -> dict[str, Any]:
    return {
        **_resume(r, maintenant),
        "description": r["description"],
        "impact": r["impact"],
        "urgence": r["urgence"],
        "sla_prise_en_charge_le": r["sla_prise_en_charge_le"],
        "resolu_le": r["resolu_le"],
        "cloture_le": r["cloture_le"],
        "transitions_possibles": transitions_possibles(MODULE, r["statut"]),
    }


def _visible(r: RowMapping, courant: dict[str, Any]) -> bool:
    if courant["transverse"]:
        return True
    return r["direction"] is None or r["direction"] == courant["direction"]


@routeur.get("", response_model=PageActivites)
async def lister(
    courant: Courant,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    statut: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    direction = None if courant["transverse"] else courant["direction"]
    lignes, total = await repo.lister(
        session, MODULE, direction=direction, statut=statut, page=page, taille=_TAILLE
    )
    maintenant = datetime.now(UTC)
    return {
        "elements": [_resume(r, maintenant) for r in lignes],
        "total": total,
        "page": page,
        "taille": _TAILLE,
    }


@routeur.post("", response_model=CreationReponse, status_code=status.HTTP_201_CREATED)
async def creer(corps: ActiviteCreation, courant: Courant, session: Session) -> dict[str, str]:
    identifiant = await creer_activite(
        session,
        MODULE,
        titre=corps.titre,
        description=corps.description,
        impact=corps.impact,
        urgence=corps.urgence,
        categorie_id=corps.categorie_id,
        direction_id=corps.direction_id,
        responsable_id=corps.responsable_id,
        acteur=courant,
    )
    return {"id": identifiant}


async def _charger_visible(
    session: AsyncSession, identifiant: str, courant: dict[str, Any]
) -> RowMapping:
    r = await repo.par_id(session, MODULE, identifiant)
    if r is None or not _visible(r, courant):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident introuvable.")
    return r


@routeur.get("/{identifiant}", response_model=ActiviteDetail)
async def detail(identifiant: str, courant: Courant, session: Session) -> dict[str, Any]:
    r = await _charger_visible(session, identifiant, courant)
    return _detail(r, datetime.now(UTC))


@routeur.post("/{identifiant}/transition", response_model=ActiviteDetail)
async def transitionner(
    identifiant: str, corps: TransitionDemande, courant: Courant, session: Session
) -> dict[str, Any]:
    await _charger_visible(session, identifiant, courant)
    try:
        await transition(session, MODULE, identifiant, corps.vers, courant)
    except ActiviteIntrouvable as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Incident introuvable."
        ) from exc
    except TransitionInterdite as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Transition interdite : {exc}"
        ) from exc
    r = await _charger_visible(session, identifiant, courant)
    return _detail(r, datetime.now(UTC))

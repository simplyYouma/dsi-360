"""Module Risques IT : liste, création, détail, transition. Criticité = probabilité × impact."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.activites import ActiviteIntrouvable, TransitionInterdite, transition
from dsi360.application.risques import creer_risque
from dsi360.domain.etats import transitions_possibles
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import activite as repo
from dsi360.interface.schemas import (
    CreationReponse,
    PageRisques,
    RisqueCreation,
    RisqueDetail,
    TransitionDemande,
)
from dsi360.interface.securite import exiger_acces

MODULE = "risque"
_ACCES = "risques"
_TAILLE = 15

routeur = APIRouter(prefix="/risques", tags=["risques"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces(_ACCES))]


def _donnees(r: RowMapping) -> dict[str, Any]:
    valeur = r["donnees"]
    if isinstance(valeur, str):
        valeur = json.loads(valeur)
    return dict(valeur) if isinstance(valeur, dict) else {}


def _responsable(r: RowMapping) -> dict[str, str] | None:
    if r["resp_email"] is None:
        return None
    return {"prenom": r["resp_prenom"], "nom": r["resp_nom"], "email": r["resp_email"]}


def _resume(r: RowMapping) -> dict[str, Any]:
    d = _donnees(r)
    return {
        "id": r["id"],
        "reference": r["reference"],
        "titre": r["titre"],
        "statut": r["statut"],
        "direction": r["direction"],
        "responsable": _responsable(r),
        "probabilite": int(d.get("probabilite", 0)),
        "impact": int(d.get("impact", 0)),
        "criticite": int(d.get("criticite", 0)),
        "cree_le": r["cree_le"],
    }


def _detail(r: RowMapping) -> dict[str, Any]:
    return {
        **_resume(r),
        "description": r["description"],
        "transitions_possibles": transitions_possibles(MODULE, r["statut"]),
    }


def _visible(r: RowMapping, courant: dict[str, Any]) -> bool:
    if courant["transverse"]:
        return True
    return r["direction"] is None or r["direction"] == courant["direction"]


async def _charger(session: AsyncSession, ident: str, courant: dict[str, Any]) -> RowMapping:
    r = await repo.par_id(session, MODULE, ident)
    if r is None or not _visible(r, courant):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risque introuvable.")
    return r


@routeur.get("", response_model=PageRisques)
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
    return {
        "elements": [_resume(r) for r in lignes],
        "total": total,
        "page": page,
        "taille": _TAILLE,
    }


@routeur.post("", response_model=CreationReponse, status_code=status.HTTP_201_CREATED)
async def creer(corps: RisqueCreation, courant: Courant, session: Session) -> dict[str, str]:
    ident = await creer_risque(
        session,
        titre=corps.titre,
        description=corps.description,
        direction_id=corps.direction_id,
        responsable_id=corps.responsable_id,
        probabilite=corps.probabilite,
        impact=corps.impact,
        acteur=courant,
    )
    return {"id": ident}


@routeur.get("/{ident}", response_model=RisqueDetail)
async def detail(ident: str, courant: Courant, session: Session) -> dict[str, Any]:
    return _detail(await _charger(session, ident, courant))


@routeur.post("/{ident}/transition", response_model=RisqueDetail)
async def transitionner(
    ident: str, corps: TransitionDemande, courant: Courant, session: Session
) -> dict[str, Any]:
    await _charger(session, ident, courant)
    try:
        await transition(session, MODULE, ident, corps.vers, courant)
    except ActiviteIntrouvable as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Introuvable.") from exc
    except TransitionInterdite as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Transition interdite : {exc}"
        ) from exc
    return _detail(await _charger(session, ident, courant))

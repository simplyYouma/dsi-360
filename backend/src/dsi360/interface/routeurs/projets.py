"""Module Projets : liste, création, détail, transition, avancement. RBAC + cloisonnement."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.activites import ActiviteIntrouvable, TransitionInterdite, transition
from dsi360.application.projets import creer_projet, maj_avancement
from dsi360.domain.etats import transitions_possibles
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.export import vers_csv, vers_xlsx
from dsi360.infrastructure.repositories import activite as repo
from dsi360.interface.schemas import (
    AvancementDemande,
    CreationReponse,
    PageProjets,
    ProjetCreation,
    ProjetDetail,
    TransitionDemande,
)
from dsi360.interface.securite import exiger_acces

MODULE = "projet"
_ACCES = "projets"
_TAILLE = 15

routeur = APIRouter(prefix="/projets", tags=["projets"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces(_ACCES))]


def _donnees(r: RowMapping) -> dict[str, Any]:
    valeur = r["donnees"]
    if isinstance(valeur, str):
        valeur = json.loads(valeur)
    return dict(valeur) if isinstance(valeur, dict) else {}


def _chef(r: RowMapping) -> dict[str, str] | None:
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
        "chef": _chef(r),
        "avancement": int(d.get("avancement", 0)),
        "budget": d.get("budget"),
        "date_fin": d.get("date_fin"),
        "cree_le": r["cree_le"],
    }


def _detail(r: RowMapping) -> dict[str, Any]:
    d = _donnees(r)
    return {
        **_resume(r),
        "description": r["description"],
        "sponsor": d.get("sponsor"),
        "date_debut": d.get("date_debut"),
        "transitions_possibles": transitions_possibles(MODULE, r["statut"]),
    }


def _visible(r: RowMapping, courant: dict[str, Any]) -> bool:
    if courant["transverse"]:
        return True
    return r["direction"] is None or r["direction"] == courant["direction"]


async def _charger(session: AsyncSession, ident: str, courant: dict[str, Any]) -> RowMapping:
    r = await repo.par_id(session, MODULE, ident)
    if r is None or not _visible(r, courant):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable.")
    return r


@routeur.get("", response_model=PageProjets)
async def lister(
    courant: Courant,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    statut: Annotated[str | None, Query()] = None,
    responsable_id: Annotated[str | None, Query()] = None,
    non_assigne: Annotated[bool, Query()] = False,
    q: Annotated[str | None, Query(max_length=80)] = None,
    etat: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    direction = None if courant["transverse"] else courant["direction"]
    lignes, total = await repo.lister(
        session,
        MODULE,
        direction=direction,
        statut=statut,
        page=page,
        taille=_TAILLE,
        responsable_id=responsable_id,
        non_assigne=non_assigne,
        q=q,
        etat=etat,
    )
    return {
        "elements": [_resume(r) for r in lignes],
        "total": total,
        "page": page,
        "taille": _TAILLE,
    }


@routeur.post("", response_model=CreationReponse, status_code=status.HTTP_201_CREATED)
async def creer(corps: ProjetCreation, courant: Courant, session: Session) -> dict[str, str]:
    ident = await creer_projet(
        session,
        titre=corps.titre,
        description=corps.description,
        direction_id=corps.direction_id,
        responsable_id=corps.responsable_id,
        sponsor=corps.sponsor,
        budget=corps.budget,
        date_debut=corps.date_debut,
        date_fin=corps.date_fin,
        acteur=courant,
    )
    return {"id": ident}


_ENTETES = ["Référence", "Projet", "Statut", "Chef de projet", "Avancement", "Échéance", "Créé le"]


@routeur.get("/export")
async def exporter(
    courant: Courant,
    session: Session,
    format: Annotated[str, Query(alias="format")] = "csv",
) -> Response:
    direction = None if courant["transverse"] else courant["direction"]
    lignes = await repo.lister_tout(session, MODULE, direction=direction)
    donnees: list[list[Any]] = []
    for r in lignes:
        d = _donnees(r)
        chef = f"{r['resp_prenom']} {r['resp_nom']}" if r["resp_email"] is not None else ""
        donnees.append(
            [
                r["reference"],
                r["titre"],
                r["statut"],
                chef,
                f"{int(d.get('avancement', 0))}%",
                d.get("date_fin") or "",
                r["cree_le"].strftime("%Y-%m-%d %H:%M"),
            ]
        )
    if format == "xlsx":
        contenu = vers_xlsx(_ENTETES, donnees, "projets")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:
        contenu = vers_csv(_ENTETES, donnees)
        media = "text/csv"
        ext = "csv"
    return Response(
        content=contenu,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=projets-export.{ext}"},
    )


@routeur.get("/{ident}", response_model=ProjetDetail)
async def detail(ident: str, courant: Courant, session: Session) -> dict[str, Any]:
    return _detail(await _charger(session, ident, courant))


@routeur.post("/{ident}/transition", response_model=ProjetDetail)
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


@routeur.patch("/{ident}/avancement", response_model=ProjetDetail)
async def avancement(
    ident: str, corps: AvancementDemande, courant: Courant, session: Session
) -> dict[str, Any]:
    await _charger(session, ident, courant)
    await maj_avancement(session, ident, corps.avancement, courant)
    return _detail(await _charger(session, ident, courant))

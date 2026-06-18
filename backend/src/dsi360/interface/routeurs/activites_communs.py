"""Fabrique de routeur d'activités, partagée par les modules (incidents, demandes, projets…).

Évite la duplication : liste paginée cloisonnée, création (priorité + SLA + audit), détail et
transition (machine à états) sont identiques d'un module à l'autre — seules changent la clé
d'accès RBAC, le module domaine et l'URL.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.activites import (
    ActiviteIntrouvable,
    TransitionInterdite,
    creer_activite,
    transition,
)
from dsi360.domain.etats import ordre_etats, transitions_possibles
from dsi360.domain.sla import statut_sla
from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.export import vers_csv, vers_xlsx
from dsi360.infrastructure.repositories import activite as repo
from dsi360.interface.schemas import (
    ActiviteCreation,
    ActiviteDetail,
    CreationReponse,
    PageActivites,
    TransitionDemande,
)
from dsi360.interface.securite import exiger_acces

_TAILLE = 15
_FENETRE_APPROCHE = timedelta(hours=2)


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


def _detail(module: str, r: RowMapping, maintenant: datetime) -> dict[str, Any]:
    return {
        **_resume(r, maintenant),
        "description": r["description"],
        "impact": r["impact"],
        "urgence": r["urgence"],
        "sla_prise_en_charge_le": r["sla_prise_en_charge_le"],
        "resolu_le": r["resolu_le"],
        "cloture_le": r["cloture_le"],
        "transitions_possibles": transitions_possibles(module, r["statut"]),
        "etats": ordre_etats(module),
    }


def _visible(r: RowMapping, courant: dict[str, Any]) -> bool:
    if courant["transverse"]:
        return True
    return r["direction"] is None or r["direction"] == courant["direction"]


ENTETES_EXPORT = [
    "Référence",
    "Titre",
    "Statut",
    "Priorité",
    "Catégorie",
    "Direction",
    "Échéance SLA",
    "Créé le",
    "Responsable",
]


def _ligne_export(r: RowMapping) -> list[Any]:
    resp = f"{r['resp_prenom']} {r['resp_nom']}" if r["resp_email"] is not None else ""
    echeance = r["sla_resolution_le"].strftime("%Y-%m-%d %H:%M") if r["sla_resolution_le"] else ""
    return [
        r["reference"],
        r["titre"],
        r["statut"],
        f"P{r['priorite']}" if r["priorite"] is not None else "",
        r["categorie"] or "",
        r["direction"] or "",
        echeance,
        r["cree_le"].strftime("%Y-%m-%d %H:%M"),
        resp,
    ]


Session = Annotated[AsyncSession, Depends(session_scope)]


def creer_routeur(module: str, acces: str, prefixe: str, tag: str) -> APIRouter:
    routeur = APIRouter(prefix=prefixe, tags=[tag])
    Courant = Annotated[dict[str, Any], Depends(exiger_acces(acces))]  # noqa: N806

    async def charger_visible(
        session: AsyncSession, ident: str, courant: dict[str, Any]
    ) -> RowMapping:
        r = await repo.par_id(session, module, ident)
        if r is None or not _visible(r, courant):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Introuvable.")
        return r

    @routeur.get("", response_model=PageActivites)
    async def lister(
        courant: Courant,
        session: Session,
        page: Annotated[int, Query(ge=1)] = 1,
        statut: Annotated[str | None, Query()] = None,
    ) -> dict[str, Any]:
        direction = None if courant["transverse"] else courant["direction"]
        lignes, total = await repo.lister(
            session, module, direction=direction, statut=statut, page=page, taille=_TAILLE
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
        ident = await creer_activite(
            session,
            module,
            titre=corps.titre,
            description=corps.description,
            impact=corps.impact,
            urgence=corps.urgence,
            categorie_id=corps.categorie_id,
            direction_id=corps.direction_id,
            responsable_id=corps.responsable_id,
            acteur=courant,
        )
        return {"id": ident}

    @routeur.get("/export")
    async def exporter(
        courant: Courant,
        session: Session,
        format: Annotated[str, Query(alias="format")] = "csv",
    ) -> Response:
        direction = None if courant["transverse"] else courant["direction"]
        lignes = await repo.lister_tout(session, module, direction=direction)
        donnees = [_ligne_export(r) for r in lignes]
        if format == "xlsx":
            contenu = vers_xlsx(ENTETES_EXPORT, donnees, tag)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ext = "xlsx"
        else:
            contenu = vers_csv(ENTETES_EXPORT, donnees)
            media = "text/csv"
            ext = "csv"
        nom = f"{prefixe.strip('/')}-export.{ext}"
        return Response(
            content=contenu,
            media_type=media,
            headers={"Content-Disposition": f"attachment; filename={nom}"},
        )

    async def detail_complet(r: RowMapping, session: AsyncSession) -> dict[str, Any]:
        base = _detail(module, r, datetime.now(UTC))
        base["historique"] = await audit.historique_statuts(session, module, r["reference"])
        return base

    @routeur.get("/{ident}", response_model=ActiviteDetail)
    async def detail(ident: str, courant: Courant, session: Session) -> dict[str, Any]:
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    @routeur.post("/{ident}/transition", response_model=ActiviteDetail)
    async def transitionner(
        ident: str, corps: TransitionDemande, courant: Courant, session: Session
    ) -> dict[str, Any]:
        await charger_visible(session, ident, courant)
        try:
            await transition(session, module, ident, corps.vers, courant)
        except ActiviteIntrouvable as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Introuvable."
            ) from exc
        except TransitionInterdite as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=f"Transition interdite : {exc}"
            ) from exc
        r = await charger_visible(session, ident, courant)
        return await detail_complet(r, session)

    return routeur

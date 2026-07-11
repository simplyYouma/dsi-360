"""Module Risques IT : liste, création, détail, transition. Criticité = probabilité × impact."""

import json
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.activites import ActiviteIntrouvable, TransitionInterdite, transition
from dsi360.application.autorisations import ACTEUR, ADMIN, capacites, charger_roles
from dsi360.application.risques import creer_risque
from dsi360.domain.etats import est_porte_validation, ordre_etats, transitions_possibles
from dsi360.domain.revue import prochaine_revue
from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import activite as repo
from dsi360.interface.schemas import (
    AssignationDemande,
    CategorieDemande,
    CreationReponse,
    PageRisques,
    RevueDemande,
    RisqueCreation,
    RisqueDetail,
    TransitionDemande,
)
from dsi360.interface.securite import (
    ContexteActivite,
    exiger_acces,
    exiger_agent_designable,
    exiger_role_activite,
)

MODULE = "risque"
_ACCES = "risques"
_TAILLE = 15

routeur = APIRouter(prefix="/risques", tags=["risques"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces(_ACCES))]
# Distribuer le travail revient à l'administrateur (ADR-0003).
CtxAdmin = Annotated[ContexteActivite, Depends(exiger_role_activite(MODULE, _ACCES, {ADMIN}))]
# Faire avancer le risque : gestionnaire, contributeurs et administrateur.
CtxActeur = Annotated[ContexteActivite, Depends(exiger_role_activite(MODULE, _ACCES, {ACTEUR}))]


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
        "responsable_id": r["resp_id"],
        "nb_commentaires": r["nb_commentaires"],
        "nb_non_vus": r["nb_non_vus"] if "nb_non_vus" in r else 0,
        "probabilite": int(d.get("probabilite", 0)),
        "impact": int(d.get("impact", 0)),
        "criticite": int(d.get("criticite", 0)),
        "cree_le": r["cree_le"],
    }


def _detail(r: RowMapping) -> dict[str, Any]:
    d = _donnees(r)
    return {
        **_resume(r),
        "description": r["description"],
        "categorie": r["categorie"],
        "categorie_id": str(r["categorie_id"]) if r["categorie_id"] is not None else None,
        "transitions_possibles": transitions_possibles(MODULE, r["statut"]),
        "etats": ordre_etats(MODULE),
        "en_attente_validation": est_porte_validation(MODULE, r["statut"]),
        "periodicite": d.get("periodicite"),
        "prochaine_revue": d.get("prochaine_revue"),
        "derniere_revue": d.get("derniere_revue"),
    }


def _visible(r: RowMapping, courant: dict[str, Any]) -> bool:
    if courant["transverse"]:
        return True
    return r["direction"] is None or r["direction"] == courant["direction"]


async def _charger(session: AsyncSession, ident: str, courant: dict[str, Any]) -> RowMapping:
    r = await repo.par_id(session, MODULE, ident, moi=courant["id"])
    if r is None or not _visible(r, courant):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risque introuvable.")
    return r


@routeur.get("", response_model=PageRisques)
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
        moi=courant["id"],
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
        categorie_id=corps.categorie_id,
        probabilite=corps.probabilite,
        impact=corps.impact,
        acteur=courant,
    )
    return {"id": ident}


async def _detail_complet(
    session: AsyncSession, r: RowMapping, courant: dict[str, Any]
) -> dict[str, Any]:
    base = _detail(r)
    base["historique"] = await audit.historique_statuts(session, MODULE, r["reference"])
    # Le serveur calcule les capacités de l'appelant ; l'écran obéit.
    base["permissions"] = capacites(await charger_roles(session, r, courant))
    return base


@routeur.get("/{ident}", response_model=RisqueDetail)
async def detail(ident: str, courant: Courant, session: Session) -> dict[str, Any]:
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.post("/{ident}/transition", response_model=RisqueDetail)
async def transitionner(
    ident: str, corps: TransitionDemande, ctx: CtxActeur, session: Session
) -> dict[str, Any]:
    courant = ctx.courant
    await _charger(session, ident, courant)
    try:
        await transition(session, MODULE, ident, corps.vers, courant)
    except ActiviteIntrouvable as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Introuvable.") from exc
    except TransitionInterdite as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Transition interdite : {exc}"
        ) from exc
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.post("/{ident}/assignation", response_model=RisqueDetail)
async def assigner(
    ident: str, corps: AssignationDemande, ctx: CtxAdmin, session: Session
) -> dict[str, Any]:
    """Confier le risque à un responsable. Seul l'administrateur distribue le travail."""
    courant, avant = ctx.courant, ctx.activite
    await exiger_agent_designable(session, corps.responsable_id, _ACCES)
    await repo.assigner(session, ident, corps.responsable_id)
    await audit.consigner(
        session,
        action="ASSIGNATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type=MODULE,
        cible_id=avant["reference"],
        ancienne={"responsable_id": avant["resp_id"]},
        nouvelle={"responsable_id": corps.responsable_id},
    )
    await session.commit()
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.post("/{ident}/categorie", response_model=RisqueDetail)
async def changer_categorie(
    ident: str, corps: CategorieDemande, ctx: CtxAdmin, session: Session
) -> dict[str, Any]:
    """La catégorie pèse sur la criticité : seul l'administrateur la fixe."""
    courant = ctx.courant
    avant = await _charger(session, ident, courant)
    if corps.categorie_id is not None:
        ok = await session.scalar(
            text("SELECT 1 FROM core.categorie WHERE id::text = :c AND module = :m"),
            {"c": corps.categorie_id, "m": MODULE},
        )
        if ok is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Catégorie inconnue pour ce module.",
            )
    await session.execute(
        text(
            "UPDATE core.activite SET categorie_id = cast(:c as uuid) "
            "WHERE id = cast(:id as uuid)"
        ),
        {"c": corps.categorie_id, "id": ident},
    )
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type=MODULE,
        cible_id=avant["reference"],
        nouvelle={"categorie_id": corps.categorie_id},
    )
    await session.commit()
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.post("/{ident}/revue", response_model=RisqueDetail)
async def planifier_revue(
    ident: str, corps: RevueDemande, ctx: CtxActeur, session: Session
) -> dict[str, Any]:
    """Planifie la revue périodique du risque (périodicité + prochaine revue)."""
    courant = ctx.courant
    avant = await _charger(session, ident, courant)
    fragment = corps.model_dump(exclude_unset=True, mode="json")
    if fragment:
        await session.execute(
            text(
                "UPDATE core.activite SET donnees = donnees || cast(:f as jsonb) "
                "WHERE id = cast(:id as uuid)"
            ),
            {"id": ident, "f": json.dumps(fragment)},
        )
        await audit.consigner(
            session,
            action="MODIFICATION",
            acteur_id=courant["id"],
            acteur_email=courant["email"],
            module=MODULE,
            cible_type=MODULE,
            cible_id=avant["reference"],
            nouvelle=fragment,
        )
        await session.commit()
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.post("/{ident}/revue/effectuee", response_model=RisqueDetail)
async def marquer_revue_effectuee(ident: str, ctx: CtxActeur, session: Session) -> dict[str, Any]:
    """Enregistre la revue du jour et reporte l'échéance suivante selon la périodicité.

    Attester qu'une revue a eu lieu engage la DSI : réservé aux acteurs du risque.
    Sans périodicité, aucune cadence n'existe : on refuse plutôt que d'inventer une date.
    """
    courant = ctx.courant
    avant = await _charger(session, ident, courant)
    periodicite = _donnees(avant).get("periodicite")
    if not periodicite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Définissez d'abord une périodicité pour cette revue.",
        )
    try:
        faite_le = datetime.now(UTC).date()
        suivante = prochaine_revue(str(periodicite), faite_le)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    fragment = {
        "derniere_revue": faite_le.isoformat(),
        "prochaine_revue": suivante.isoformat(),
    }
    # `revue_notifiee_le` est retiré : la nouvelle échéance doit pouvoir rappeler.
    await session.execute(
        text(
            "UPDATE core.activite SET donnees = "
            "(donnees - 'revue_notifiee_le') || cast(:f as jsonb) WHERE id = cast(:id as uuid)"
        ),
        {"id": ident, "f": json.dumps(fragment)},
    )
    await audit.consigner(
        session,
        action="REVUE_EFFECTUEE",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type=MODULE,
        cible_id=avant["reference"],
        ancienne={"prochaine_revue": _donnees(avant).get("prochaine_revue")},
        nouvelle=fragment,
    )
    await session.commit()
    return await _detail_complet(session, await _charger(session, ident, courant), courant)

"""Module Projets : liste, création, détail, transition, avancement. RBAC + cloisonnement."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.activites import ActiviteIntrouvable, TransitionInterdite, transition
from dsi360.application.autorisations import ACTEUR, capacites, charger_roles
from dsi360.application.projets import creer_projet, maj_projet
from dsi360.application.taches import creer_tache, maj_tache, supprimer_tache
from dsi360.domain.etats import transitions_possibles
from dsi360.domain.texte import phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.export import vers_csv, vers_xlsx
from dsi360.infrastructure.repositories import activite as repo
from dsi360.infrastructure.repositories import jalon as jalon_repo
from dsi360.infrastructure.repositories import tache as tache_repo
from dsi360.interface.routeurs.documents_communs import enregistrer_documents
from dsi360.interface.routeurs.liens_communs import enregistrer_liens
from dsi360.interface.schemas import (
    CreationReponse,
    JalonCreation,
    JalonItem,
    JalonMaj,
    NoteCreation,
    NoteItem,
    PageProjets,
    ProjetCreation,
    ProjetDetail,
    ProjetMaj,
    ReordreTaches,
    Tache,
    TacheCreation,
    TacheMaj,
    TransitionDemande,
)
from dsi360.interface.securite import (
    ContexteActivite,
    exiger_acces,
    exiger_admin,
    exiger_agent_designable,
    exiger_champs_tache,
    exiger_role_activite,
    exiger_role_activite_courant,
)

MODULE = "projet"
_ACCES = "projets"
_TAILLE = 15

routeur = APIRouter(prefix="/projets", tags=["projets"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(exiger_acces(_ACCES))]
# Faire avancer le projet : administrateur, chef de projet et contributeurs. Lire reste ouvert.
Acteur = Annotated[dict[str, Any], Depends(exiger_role_activite_courant(MODULE, _ACCES, {ACTEUR}))]
# Aucun rôle exigé : il suffit de voir le projet. La route tranche ensuite champ par champ.
CtxLecture = Annotated[ContexteActivite, Depends(exiger_role_activite(MODULE, _ACCES))]


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
        "responsable_id": r["resp_id"],
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


async def _detail_complet(
    session: AsyncSession, r: RowMapping, courant: dict[str, Any]
) -> dict[str, Any]:
    """Détail + capacités de l'appelant. Le serveur calcule, l'écran obéit."""
    base = _detail(r)
    base["permissions"] = capacites(await charger_roles(session, r, courant))
    return base


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
    """Ouvrir un projet est permis à tout profil du module ; en nommer le chef ne l'est pas.

    Le créateur ne devient donc acteur que si l'administrateur le désigne — c'est lui qui distribue.
    """
    if corps.responsable_id is not None:
        exiger_admin(courant)
        await exiger_agent_designable(session, corps.responsable_id, _ACCES)
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


@routeur.patch("/{ident}", response_model=ProjetDetail)
async def modifier(
    ident: str, corps: ProjetMaj, courant: Acteur, session: Session
) -> dict[str, Any]:
    await _charger(session, ident, courant)
    champs = corps.model_dump(exclude_unset=True)
    # Changer de chef de projet, c'est redistribuer le travail : réservé à l'administrateur.
    # Le reste du cadrage (titre, sponsor, budget, dates) reste ouvert aux acteurs.
    if "responsable_id" in champs:
        exiger_admin(courant)
        await exiger_agent_designable(session, champs["responsable_id"], _ACCES)
    if champs:
        await maj_projet(session, ident, champs, courant)
        await session.commit()
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


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
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


# Transitions qui doivent être justifiées : la justification est enregistrée comme note.
_TRANSITIONS_JUSTIFIEES = frozenset({"Suspendu", "Clôturé"})


@routeur.post("/{ident}/transition", response_model=ProjetDetail)
async def transitionner(
    ident: str, corps: TransitionDemande, courant: Acteur, session: Session
) -> dict[str, Any]:
    await _charger(session, ident, courant)
    if corps.vers in _TRANSITIONS_JUSTIFIEES and not (corps.note or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Une note de justification est requise pour « {corps.vers} ».",
        )
    try:
        await transition(session, MODULE, ident, corps.vers, courant)
    except ActiviteIntrouvable as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Introuvable.") from exc
    except TransitionInterdite as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Transition interdite : {exc}"
        ) from exc
    # La justification rejoint le journal de bord, rattachée à l'état cible.
    if corps.vers in _TRANSITIONS_JUSTIFIEES:
        await session.execute(
            text(
                "INSERT INTO core.note (activite_id, texte, contexte, auteur_email) "
                "VALUES (cast(:aid as uuid), :texte, :ctx, :email)"
            ),
            {
                "aid": ident,
                "texte": (corps.note or "").strip(),
                "ctx": corps.vers,
                "email": courant["email"],
            },
        )
        await session.commit()
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


# --- Journal de bord (notes) & liens utiles ---


@routeur.get("/{ident}/notes", response_model=list[NoteItem])
async def lister_notes(ident: str, courant: Courant, session: Session) -> list[dict[str, Any]]:
    await _charger(session, ident, courant)
    lignes = (
        await session.execute(
            text(
                "SELECT n.id::text AS id, n.texte, n.contexte, n.auteur_email AS auteur, "
                "n.cree_le FROM core.note n WHERE n.activite_id = cast(:id as uuid) "
                "ORDER BY n.cree_le DESC"
            ),
            {"id": ident},
        )
    ).mappings().all()
    return [dict(x) for x in lignes]


@routeur.post("/{ident}/notes", response_model=NoteItem, status_code=status.HTTP_201_CREATED)
async def creer_note(
    ident: str, corps: NoteCreation, courant: Acteur, session: Session
) -> dict[str, Any]:
    projet = await _charger(session, ident, courant)
    ligne = (
        await session.execute(
            text(
                "INSERT INTO core.note (activite_id, texte, auteur_email) "
                "VALUES (cast(:aid as uuid), :texte, :email) "
                "RETURNING id::text AS id, texte, contexte, auteur_email AS auteur, cree_le"
            ),
            {"aid": ident, "texte": corps.texte.strip(), "email": courant["email"]},
        )
    ).mappings().one()
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type="note",
        cible_id=projet["reference"],
        nouvelle={"texte": corps.texte.strip()[:200]},
    )
    await session.commit()
    return dict(ligne)


# Liens utiles (projet + tâches) : logique partagée avec les changements.
enregistrer_liens(
    routeur,
    module=MODULE,
    charger=_charger,
    Courant=Courant,
    Session=Session,
    CourantEcriture=Acteur,
)


# --- Tâches (l'avancement et le passage « En cours » se déduisent d'elles) ---


def _tache_resume(r: RowMapping) -> dict[str, Any]:
    assigne = None
    if r["assigne_email"] is not None:
        assigne = {
            "prenom": r["assigne_prenom"],
            "nom": r["assigne_nom"],
            "email": r["assigne_email"],
        }
    return {
        "id": r["id"],
        "titre": r["titre"],
        "description": r["description"],
        "statut": r["statut"],
        "assigne": assigne,
        "assigne_id": r["assigne_id"],
        "echeance": r["echeance"],
        "ordre": r["ordre"],
        "nb_commentaires": r["nb_commentaires"],
        "nb_non_vus": r["nb_non_vus"] if "nb_non_vus" in r else 0,
    }


async def _charger_tache(
    session: AsyncSession, ident: str, tache_id: str, courant: dict[str, Any]
) -> RowMapping:
    await _charger(session, ident, courant)  # vérifie l'accès au projet
    t = await tache_repo.par_id(session, tache_id, moi=courant["id"])
    if t is None or t["activite_id"] != ident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")
    return t


@routeur.get("/{ident}/taches", response_model=list[Tache])
async def lister_taches(
    ident: str, courant: Courant, session: Session
) -> list[dict[str, Any]]:
    await _charger(session, ident, courant)
    return [
        _tache_resume(t) for t in await tache_repo.lister(session, ident, moi=courant["id"])
    ]


@routeur.post("/{ident}/taches", response_model=ProjetDetail, status_code=status.HTTP_201_CREATED)
async def creer_tache_projet(
    ident: str, corps: TacheCreation, courant: Acteur, session: Session
) -> dict[str, Any]:
    await _charger(session, ident, courant)
    await exiger_agent_designable(session, corps.assigne_id, _ACCES)
    await creer_tache(
        session,
        ident,
        MODULE,
        {
            "titre": phrase_propre(corps.titre),
            "description": corps.description,
            "assigne_id": corps.assigne_id,
            "echeance": corps.echeance,
            "ordre": corps.ordre,
        },
        courant,
    )
    await session.commit()
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.patch("/{ident}/taches/{tache_id}", response_model=ProjetDetail)
async def maj_tache_projet(
    ident: str, tache_id: str, corps: TacheMaj, ctx: CtxLecture, session: Session
) -> dict[str, Any]:
    """Les acteurs modifient tout ; l'assigné de cette tâche n'en change que le statut."""
    courant = ctx.courant
    tache = await _charger_tache(session, ident, tache_id, courant)
    champs = corps.model_dump(exclude_unset=True)
    exiger_champs_tache(ctx.roles, tache, courant, champs)
    await exiger_agent_designable(session, champs.get("assigne_id"), _ACCES)
    if "titre" in champs and champs["titre"] is not None:
        champs["titre"] = phrase_propre(champs["titre"])
    await maj_tache(session, dict(tache), MODULE, champs, courant)
    await session.commit()
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.delete("/{ident}/taches/{tache_id}", response_model=ProjetDetail)
async def supprimer_tache_projet(
    ident: str, tache_id: str, courant: Acteur, session: Session
) -> dict[str, Any]:
    tache = await _charger_tache(session, ident, tache_id, courant)
    await supprimer_tache(session, dict(tache), MODULE, courant)
    await session.commit()
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


@routeur.patch("/{ident}/taches", response_model=ProjetDetail)
async def reordonner_taches_projet(
    ident: str, corps: ReordreTaches, courant: Acteur, session: Session
) -> dict[str, Any]:
    await _charger(session, ident, courant)
    await tache_repo.reordonner(session, ident, corps.ordre)
    await session.commit()
    return await _detail_complet(session, await _charger(session, ident, courant), courant)


# --- Jalons (dates clés du projet) ---


async def _charger_jalon(
    session: AsyncSession, ident: str, jalon_id: str, courant: dict[str, Any]
) -> RowMapping:
    await _charger(session, ident, courant)
    j = await jalon_repo.par_id(session, jalon_id, ident)
    if j is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jalon introuvable.")
    return j


async def _auditer_jalon(
    session: AsyncSession, ident: str, courant: dict[str, Any], action: str, detail: dict[str, Any]
) -> None:
    projet = await _charger(session, ident, courant)
    await audit.consigner(
        session,
        action=action,
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type="jalon",
        cible_id=projet["reference"],
        nouvelle=detail,
    )


@routeur.get("/{ident}/jalons", response_model=list[JalonItem])
async def lister_jalons(ident: str, courant: Courant, session: Session) -> list[dict[str, Any]]:
    await _charger(session, ident, courant)
    return [dict(j) for j in await jalon_repo.lister(session, ident)]


@routeur.post("/{ident}/jalons", response_model=JalonItem, status_code=status.HTTP_201_CREATED)
async def creer_jalon(
    ident: str, corps: JalonCreation, courant: Acteur, session: Session
) -> dict[str, Any]:
    await _charger(session, ident, courant)
    ligne = await jalon_repo.creer(
        session,
        ident,
        {"titre": phrase_propre(corps.titre), "echeance": corps.echeance, "ordre": corps.ordre},
    )
    await _auditer_jalon(session, ident, courant, "CREATION", {"titre": corps.titre})
    await session.commit()
    return dict(ligne)


@routeur.patch("/{ident}/jalons/{jalon_id}", response_model=JalonItem)
async def maj_jalon(
    ident: str, jalon_id: str, corps: JalonMaj, courant: Acteur, session: Session
) -> dict[str, Any]:
    await _charger_jalon(session, ident, jalon_id, courant)
    champs = corps.model_dump(exclude_unset=True)
    if champs.get("titre") is not None:
        champs["titre"] = phrase_propre(champs["titre"])
    await jalon_repo.maj(session, jalon_id, champs)
    await _auditer_jalon(session, ident, courant, "MODIFICATION", champs)
    await session.commit()
    j = await jalon_repo.par_id(session, jalon_id, ident)
    return dict(j) if j is not None else {}


@routeur.delete("/{ident}/jalons/{jalon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_jalon(
    ident: str, jalon_id: str, courant: Acteur, session: Session
) -> None:
    jalon = await _charger_jalon(session, ident, jalon_id, courant)
    await jalon_repo.supprimer(session, jalon_id)
    await _auditer_jalon(session, ident, courant, "SUPPRESSION", {"titre": jalon["titre"]})
    await session.commit()


# Pièces jointes (activité + tâches) : logique partagée avec les autres modules.
enregistrer_documents(
    routeur, module=MODULE, charger=_charger, Courant=Courant, CourantEcriture=Acteur
)

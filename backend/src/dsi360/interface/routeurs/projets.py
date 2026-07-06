"""Module Projets : liste, création, détail, transition, avancement. RBAC + cloisonnement."""

import io
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.activites import ActiviteIntrouvable, TransitionInterdite, transition
from dsi360.application.projets import creer_projet, maj_projet
from dsi360.application.taches import creer_tache, maj_tache, supprimer_tache
from dsi360.config import get_settings
from dsi360.domain.etats import transitions_possibles
from dsi360.domain.texte import phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.export import vers_csv, vers_xlsx
from dsi360.infrastructure.repositories import activite as repo
from dsi360.infrastructure.repositories import tache as tache_repo
from dsi360.interface.schemas import (
    CreationReponse,
    DocumentItem,
    DocumentRenommage,
    PageProjets,
    ProjetCreation,
    ProjetDetail,
    ProjetMaj,
    Tache,
    TacheCreation,
    TacheMaj,
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


@routeur.patch("/{ident}", response_model=ProjetDetail)
async def modifier(
    ident: str, corps: ProjetMaj, courant: Courant, session: Session
) -> dict[str, Any]:
    await _charger(session, ident, courant)
    champs = corps.model_dump(exclude_unset=True)
    if champs.get("responsable_id") is not None:
        existe = await session.scalar(
            text("SELECT 1 FROM core.utilisateur WHERE id::text = :id AND actif"),
            {"id": champs["responsable_id"]},
        )
        if existe is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Agent introuvable ou inactif."
            )
    if champs:
        await maj_projet(session, ident, champs, courant)
        await session.commit()
    return _detail(await _charger(session, ident, courant))


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
    }


async def _charger_tache(
    session: AsyncSession, ident: str, tache_id: str, courant: dict[str, Any]
) -> RowMapping:
    await _charger(session, ident, courant)  # vérifie l'accès au projet
    t = await tache_repo.par_id(session, tache_id)
    if t is None or t["activite_id"] != ident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")
    return t


@routeur.get("/{ident}/taches", response_model=list[Tache])
async def lister_taches(
    ident: str, courant: Courant, session: Session
) -> list[dict[str, Any]]:
    await _charger(session, ident, courant)
    return [_tache_resume(t) for t in await tache_repo.lister(session, ident)]


@routeur.post("/{ident}/taches", response_model=ProjetDetail, status_code=status.HTTP_201_CREATED)
async def creer_tache_projet(
    ident: str, corps: TacheCreation, courant: Courant, session: Session
) -> dict[str, Any]:
    await _charger(session, ident, courant)
    if corps.assigne_id is not None:
        existe = await session.scalar(
            text("SELECT 1 FROM core.utilisateur WHERE id::text = :id AND actif"),
            {"id": corps.assigne_id},
        )
        if existe is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Agent introuvable ou inactif."
            )
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
    return _detail(await _charger(session, ident, courant))


@routeur.patch("/{ident}/taches/{tache_id}", response_model=ProjetDetail)
async def maj_tache_projet(
    ident: str, tache_id: str, corps: TacheMaj, courant: Courant, session: Session
) -> dict[str, Any]:
    tache = await _charger_tache(session, ident, tache_id, courant)
    champs = corps.model_dump(exclude_unset=True)
    if champs.get("assigne_id") is not None:
        existe = await session.scalar(
            text("SELECT 1 FROM core.utilisateur WHERE id::text = :id AND actif"),
            {"id": champs["assigne_id"]},
        )
        if existe is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Agent introuvable ou inactif."
            )
    if "titre" in champs and champs["titre"] is not None:
        champs["titre"] = phrase_propre(champs["titre"])
    await maj_tache(session, dict(tache), MODULE, champs, courant)
    await session.commit()
    return _detail(await _charger(session, ident, courant))


@routeur.delete("/{ident}/taches/{tache_id}", response_model=ProjetDetail)
async def supprimer_tache_projet(
    ident: str, tache_id: str, courant: Courant, session: Session
) -> dict[str, Any]:
    tache = await _charger_tache(session, ident, tache_id, courant)
    await supprimer_tache(session, dict(tache), MODULE, courant)
    await session.commit()
    return _detail(await _charger(session, ident, courant))


# --- Documents (pièces jointes) ---

# Types autorisés (contrôle par extension). Pas d'exécutable : les fichiers sont stockés en bytea.
_EXT_DOC_AUTORISEES: frozenset[str] = frozenset(
    {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".gif",
     ".txt", ".csv", ".zip"}
)
_DOC_COLS = "id::text AS id, nom, type_mime, taille, depose_par, depose_le"


async def _lire_fichier_valide(fichier: UploadFile) -> tuple[str, bytes]:
    """Valide extension + taille et renvoie (nom nettoyé, contenu). Lève HTTPException sinon."""
    nom = (fichier.filename or "document").strip()
    ext = f".{nom.rsplit('.', 1)[-1].lower()}" if "." in nom else ""
    if ext not in _EXT_DOC_AUTORISEES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Type de fichier non autorisé."
        )
    contenu = await fichier.read()
    maxi = get_settings().max_upload_mb * 1024 * 1024
    if len(contenu) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Fichier vide."
        )
    if len(contenu) > maxi:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fichier trop volumineux (max {get_settings().max_upload_mb} Mo).",
        )
    return nom, contenu


async def _inserer_document(
    session: AsyncSession,
    *,
    activite_id: str,
    tache_id: str | None,
    fichier: UploadFile,
    nom: str,
    contenu: bytes,
    courant: dict[str, Any],
) -> dict[str, Any]:
    ligne = (
        await session.execute(
            text(
                "INSERT INTO core.document "
                "(activite_id, tache_id, nom, type_mime, taille, contenu, depose_par) "
                "VALUES (cast(:a as uuid), cast(:t as uuid), :nom, :mime, :taille, :contenu, :par) "
                f"RETURNING {_DOC_COLS}"
            ),
            {
                "a": activite_id,
                "t": tache_id,
                "nom": nom,
                "mime": fichier.content_type or "application/octet-stream",
                "taille": len(contenu),
                "contenu": contenu,
                "par": courant["email"],
            },
        )
    ).mappings().one()
    return dict(ligne)


@routeur.get("/{ident}/documents", response_model=list[DocumentItem])
async def lister_documents(
    ident: str, courant: Courant, session: Session
) -> list[dict[str, Any]]:
    await _charger(session, ident, courant)
    lignes = await session.execute(
        text(
            f"SELECT {_DOC_COLS} FROM core.document "
            "WHERE activite_id = cast(:a as uuid) AND tache_id IS NULL ORDER BY depose_le DESC"
        ),
        {"a": ident},
    )
    return [dict(x) for x in lignes.mappings().all()]


@routeur.post(
    "/{ident}/documents", response_model=DocumentItem, status_code=status.HTTP_201_CREATED
)
async def deposer_document(
    ident: str, fichier: UploadFile, courant: Courant, session: Session
) -> dict[str, Any]:
    projet = await _charger(session, ident, courant)
    nom, contenu = await _lire_fichier_valide(fichier)
    ligne = await _inserer_document(
        session, activite_id=ident, tache_id=None, fichier=fichier, nom=nom,
        contenu=contenu, courant=courant,
    )
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type="document",
        cible_id=f"{projet['reference']}/{nom}",
    )
    return dict(ligne)


_VIGNETTE_PX = 240


def _vignette(contenu: bytes, type_mime: str) -> tuple[bytes, str]:
    """Redimensionne une image en miniature (côté serveur). Retombe sur l'original si illisible."""
    try:
        img = Image.open(io.BytesIO(contenu))
        img.thumbnail((_VIGNETTE_PX, _VIGNETTE_PX))
        tampon = io.BytesIO()
        if img.mode in ("RGBA", "P", "LA"):
            img.save(tampon, format="PNG")
            return tampon.getvalue(), "image/png"
        img.convert("RGB").save(tampon, format="JPEG", quality=80)
        return tampon.getvalue(), "image/jpeg"
    except (UnidentifiedImageError, OSError):
        return contenu, type_mime


@routeur.get("/{ident}/documents/{doc_id}")
async def telecharger_document(
    ident: str,
    doc_id: str,
    courant: Courant,
    session: Session,
    taille: Annotated[str | None, Query()] = None,
) -> Response:
    await _charger(session, ident, courant)
    ligne = (
        await session.execute(
            text(
                "SELECT nom, type_mime, contenu FROM core.document "
                "WHERE id = cast(:d as uuid) AND activite_id = cast(:a as uuid)"
            ),
            {"d": doc_id, "a": ident},
        )
    ).mappings().first()
    if ligne is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable.")
    contenu = bytes(ligne["contenu"])
    type_mime = ligne["type_mime"]
    if taille == "vignette" and type_mime.startswith("image/"):
        contenu, type_mime = _vignette(contenu, type_mime)
        return Response(content=contenu, media_type=type_mime)
    return Response(
        content=contenu,
        media_type=type_mime,
        headers={"Content-Disposition": f'attachment; filename="{ligne["nom"]}"'},
    )


@routeur.patch("/{ident}/documents/{doc_id}", response_model=DocumentItem)
async def renommer_document(
    ident: str, doc_id: str, corps: DocumentRenommage, courant: Courant, session: Session
) -> dict[str, Any]:
    projet = await _charger(session, ident, courant)
    nom = corps.nom.strip()
    # On conserve l'extension d'origine si l'utilisateur ne la remet pas (fichier ouvrable).
    ancien = await session.scalar(
        text(
            "SELECT nom FROM core.document "
            "WHERE id = cast(:d as uuid) AND activite_id = cast(:a as uuid)"
        ),
        {"d": doc_id, "a": ident},
    )
    if ancien is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable.")
    if "." in ancien:
        ext = ancien.rsplit(".", 1)[-1]
        if not nom.lower().endswith(f".{ext.lower()}"):
            nom = f"{nom}.{ext}"
    ligne = (
        await session.execute(
            text(
                "UPDATE core.document SET nom = :nom "
                "WHERE id = cast(:d as uuid) AND activite_id = cast(:a as uuid) "
                f"RETURNING {_DOC_COLS}"
            ),
            {"nom": nom, "d": doc_id, "a": ident},
        )
    ).mappings().one()
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type="document",
        cible_id=f"{projet['reference']}/{nom}",
    )
    await session.commit()
    return dict(ligne)


@routeur.delete("/{ident}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_document(
    ident: str, doc_id: str, courant: Courant, session: Session
) -> None:
    projet = await _charger(session, ident, courant)
    ligne = (
        await session.execute(
            text(
                "DELETE FROM core.document "
                "WHERE id = cast(:d as uuid) AND activite_id = cast(:a as uuid) RETURNING nom"
            ),
            {"d": doc_id, "a": ident},
        )
    ).mappings().first()
    if ligne is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable.")
    await audit.consigner(
        session,
        action="SUPPRESSION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type="document",
        cible_id=f"{projet['reference']}/{ligne['nom']}",
    )


# --- Documents rattachés à une tâche (téléchargement/suppression via les routes /documents) ---


@routeur.get("/{ident}/taches/{tache_id}/documents", response_model=list[DocumentItem])
async def lister_documents_tache(
    ident: str, tache_id: str, courant: Courant, session: Session
) -> list[dict[str, Any]]:
    await _charger_tache(session, ident, tache_id, courant)
    lignes = await session.execute(
        text(
            f"SELECT {_DOC_COLS} FROM core.document "
            "WHERE tache_id = cast(:t as uuid) ORDER BY depose_le DESC"
        ),
        {"t": tache_id},
    )
    return [dict(x) for x in lignes.mappings().all()]


@routeur.post(
    "/{ident}/taches/{tache_id}/documents",
    response_model=DocumentItem,
    status_code=status.HTTP_201_CREATED,
)
async def deposer_document_tache(
    ident: str, tache_id: str, fichier: UploadFile, courant: Courant, session: Session
) -> dict[str, Any]:
    projet = await _charger(session, ident, courant)
    tache = await _charger_tache(session, ident, tache_id, courant)
    nom, contenu = await _lire_fichier_valide(fichier)
    ligne = await _inserer_document(
        session, activite_id=ident, tache_id=tache_id, fichier=fichier, nom=nom,
        contenu=contenu, courant=courant,
    )
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module=MODULE,
        cible_type="document",
        cible_id=f"{projet['reference']}/{tache['titre']}/{nom}",
    )
    return dict(ligne)

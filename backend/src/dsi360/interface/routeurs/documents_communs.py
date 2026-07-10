"""Pièces jointes d'une activité et de ses tâches — logique partagée entre modules.

Fournit :meth:`enregistrer_documents`, qui ajoute à un routeur d'activités les endpoints de
dépôt / liste / téléchargement / aperçu / renommage / suppression, au niveau de l'activité
(``/{ident}/documents``) et de chaque tâche (``/{ident}/taches/{tache_id}/documents``).

Contenu stocké en base (bytea) : sauvegardé avec la DB, transactionnel, sans infra supplémentaire.
Contrôle par extension (pas d'exécutable). Partagé par les projets et la fabrique d'activités
(changements…) : une seule implémentation, cohérente d'un module à l'autre.
"""

import io
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.config import get_settings
from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.repositories import tache as tache_repo
from dsi360.interface.schemas import DocumentItem, DocumentRenommage

Session = Annotated[AsyncSession, Depends(session_scope)]

# Types autorisés (contrôle par extension). Pas d'exécutable : les fichiers sont stockés en bytea.
_EXT_DOC_AUTORISEES: frozenset[str] = frozenset(
    {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".gif",
     ".txt", ".csv", ".zip"}
)
_DOC_COLS = "id::text AS id, nom, type_mime, taille, depose_par, depose_le"
_VIGNETTE_PX = 240


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


def enregistrer_documents(
    routeur: APIRouter,
    *,
    module: str,
    charger: Callable[[AsyncSession, str, dict[str, Any]], Awaitable[RowMapping]],
    Courant: Any,  # noqa: N803 - annotation FastAPI (Depends), même nom que la variable locale
    CourantEcriture: Any,  # noqa: N803
) -> None:
    """Ajoute les endpoints de pièces jointes (activité + tâches) à un routeur d'activités.

    `charger(session, ident, courant)` doit renvoyer l'activité (avec `reference`) ou lever 404.

    ``CourantEcriture`` garde le dépôt, le renommage et la suppression : consulter reste ouvert à
    qui voit l'activité.
    """

    async def _charger_tache(
        session: AsyncSession, ident: str, tache_id: str, courant: dict[str, Any]
    ) -> RowMapping:
        await charger(session, ident, courant)
        t = await tache_repo.par_id(session, tache_id)
        if t is None or t["activite_id"] != ident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")
        return t

    @routeur.get("/{ident}/documents", response_model=list[DocumentItem])
    async def lister_documents(
        ident: str, courant: Courant, session: Session
    ) -> list[dict[str, Any]]:
        await charger(session, ident, courant)
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
        ident: str, fichier: UploadFile, courant: CourantEcriture, session: Session
    ) -> dict[str, Any]:
        r = await charger(session, ident, courant)
        nom, contenu = await _lire_fichier_valide(fichier)
        ligne = await _inserer_document(
            session, activite_id=ident, tache_id=None, fichier=fichier, nom=nom,
            contenu=contenu, courant=courant,
        )
        await audit.consigner(
            session, action="CREATION", acteur_id=courant["id"], acteur_email=courant["email"],
            module=module, cible_type="document", cible_id=f"{r['reference']}/{nom}",
        )
        return dict(ligne)

    @routeur.get("/{ident}/documents/{doc_id}")
    async def telecharger_document(
        ident: str,
        doc_id: str,
        courant: Courant,
        session: Session,
        taille: Annotated[str | None, Query()] = None,
    ) -> Response:
        await charger(session, ident, courant)
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable."
            )
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
        ident: str,
        doc_id: str,
        corps: DocumentRenommage,
        courant: CourantEcriture,
        session: Session,
    ) -> dict[str, Any]:
        r = await charger(session, ident, courant)
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable."
            )
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
            session, action="MODIFICATION", acteur_id=courant["id"], acteur_email=courant["email"],
            module=module, cible_type="document", cible_id=f"{r['reference']}/{nom}",
        )
        await session.commit()
        return dict(ligne)

    @routeur.delete("/{ident}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def supprimer_document(
        ident: str, doc_id: str, courant: CourantEcriture, session: Session
    ) -> None:
        r = await charger(session, ident, courant)
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable."
            )
        await audit.consigner(
            session, action="SUPPRESSION", acteur_id=courant["id"], acteur_email=courant["email"],
            module=module, cible_type="document", cible_id=f"{r['reference']}/{ligne['nom']}",
        )

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
        ident: str, tache_id: str, fichier: UploadFile, courant: CourantEcriture, session: Session
    ) -> dict[str, Any]:
        r = await charger(session, ident, courant)
        tache = await _charger_tache(session, ident, tache_id, courant)
        nom, contenu = await _lire_fichier_valide(fichier)
        ligne = await _inserer_document(
            session, activite_id=ident, tache_id=tache_id, fichier=fichier, nom=nom,
            contenu=contenu, courant=courant,
        )
        await audit.consigner(
            session, action="CREATION", acteur_id=courant["id"], acteur_email=courant["email"],
            module=module, cible_type="document",
            cible_id=f"{r['reference']}/{tache['titre']}/{nom}",
        )
        return dict(ligne)

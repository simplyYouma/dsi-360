"""Fil de discussion interne DSI rattaché à une activité (tous modules).

Le demandeur n'a pas accès à la plateforme : ces échanges sont internes. Cloisonnement
par direction (un non-transverse ne commente que les activités de son périmètre).

Chaque **tâche** a aussi son propre fil (paramètre ``tache``) : le fil de l'activité n'affiche
que les commentaires sans tâche, celui d'une tâche uniquement les siens.
"""

import io
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from PIL import Image, UnidentifiedImageError
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from dsi360.application.notifications import notifier, notifier_acteurs
from dsi360.config import get_settings
from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.infrastructure.export import vers_csv, vers_xlsx
from dsi360.interface.schemas import (
    CommentaireCreation,
    CommentaireItem,
    CommentaireMaj,
    LecteurCommentaire,
)
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/commentaires", tags=["commentaires"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]

# Le fil n'accepte que des images. Le format est établi en **décodant** le fichier : l'extension
# ou le type MIME déclarés par le client ne prouvent rien.
_FORMATS_IMAGE: dict[str, str] = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}
_MAX_IMAGES = 6


async def _lire_image_valide(fichier: UploadFile) -> tuple[str, bytes, str, int, int]:
    """Valide taille et contenu réel. Renvoie (nom, octets, type MIME, largeur, hauteur)."""
    contenu = await fichier.read()
    maxi = get_settings().max_upload_mb * 1024 * 1024
    if not contenu:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Image vide.")
    if len(contenu) > maxi:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image trop volumineuse (max {get_settings().max_upload_mb} Mo).",
        )
    try:
        with Image.open(io.BytesIO(contenu)) as img:
            img.verify()  # rejette un fichier corrompu ou qui n'est pas une image
        with Image.open(io.BytesIO(contenu)) as img:
            format_ = (img.format or "").upper()
            largeur, hauteur = img.size
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Seules les images sont acceptées dans la discussion.",
        ) from exc
    type_mime = _FORMATS_IMAGE.get(format_)
    if type_mime is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Format d'image non pris en charge ({format_ or 'inconnu'}).",
        )
    nom = (fichier.filename or "image").strip()[:120]
    return nom, contenu, type_mime, largeur, hauteur


_IMAGES_DU_FIL = text(
    "SELECT commentaire_id, id::text AS id, nom, type_mime, largeur, hauteur "
    "FROM core.commentaire_image WHERE commentaire_id IN :ids ORDER BY depose_le, id"
).bindparams(bindparam("ids", expanding=True))


async def _images_du_commentaire(
    session: AsyncSession, commentaire_id: int
) -> list[dict[str, Any]]:
    lignes = (
        await session.execute(
            text(
                "SELECT id::text AS id, nom, type_mime, largeur, hauteur "
                "FROM core.commentaire_image WHERE commentaire_id = :cid ORDER BY depose_le, id"
            ),
            {"cid": commentaire_id},
        )
    ).mappings().all()
    return [dict(x) for x in lignes]


async def _exiger_activite_visible(
    session: AsyncSession, courant: dict[str, Any], ident: str
) -> str:
    """Vérifie que l'activité existe et est dans le périmètre ; renvoie sa référence."""
    ligne = (
        await session.execute(
            text(
                "SELECT a.reference, a.module, d.code AS direction "
                "FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id "
                "WHERE a.id::text = :id"
            ),
            {"id": ident},
        )
    ).mappings().first()
    if ligne is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activité introuvable.")
    # La discussion interne est ouverte à tous les agents de la DSI (collaboration transverse) :
    # on ne filtre QUE le périmètre direction, pas l'accès au module. Choix métier assumé.
    if not courant["transverse"] and ligne["direction"] not in (None, courant["direction"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hors périmètre.")
    return str(ligne["reference"])


def _sql_liste(colonne: str, avec_tache: bool = True) -> TextClause:
    """Fil d'un sujet (activité ou équipement). La colonne vient d'une liste blanche, jamais
    de l'appelant : `colonne` n'est fourni qu'ici, par les deux constantes ci-dessous."""
    filtre_tache = (
        " AND (cast(:tache as text) IS NULL AND c.tache_id IS NULL OR c.tache_id::text = :tache)"
        if avec_tache
        else ""
    )
    return text(
        "SELECT c.id, c.texte, c.cree_le, c.auteur_id::text AS auteur_id, "
        "coalesce(u.prenom || ' ' || u.nom, c.auteur_email) AS auteur, "
        "(c.maj_le IS NOT NULL) AS edite, "
        "(SELECT count(*) FROM core.commentaire_vue v "
        " WHERE v.commentaire_id = c.id AND v.utilisateur_id <> c.auteur_id) AS nb_vues, "
        "EXISTS (SELECT 1 FROM core.commentaire_vue v "
        "        WHERE v.commentaire_id = c.id AND v.utilisateur_id = cast(:moi as uuid)) AS vu "
        "FROM core.commentaire c LEFT JOIN core.utilisateur u ON u.id = c.auteur_id "
        f"WHERE c.{colonne} = cast(:id as uuid)" + filtre_tache + " ORDER BY c.cree_le"
    )


_LISTE_EQUIPEMENT = _sql_liste("equipement_id", avec_tache=False)

_LISTE = text(
    "SELECT c.id, c.texte, c.cree_le, c.auteur_id::text AS auteur_id, "
    "coalesce(u.prenom || ' ' || u.nom, c.auteur_email) AS auteur, "
    "(c.maj_le IS NOT NULL) AS edite, "
    "(SELECT count(*) FROM core.commentaire_vue v "
    " WHERE v.commentaire_id = c.id AND v.utilisateur_id <> c.auteur_id) AS nb_vues, "
    "EXISTS (SELECT 1 FROM core.commentaire_vue v "
    "        WHERE v.commentaire_id = c.id AND v.utilisateur_id = cast(:moi as uuid)) AS vu "
    "FROM core.commentaire c LEFT JOIN core.utilisateur u ON u.id = c.auteur_id "
    "WHERE c.activite_id = cast(:id as uuid) "
    "AND (cast(:tache as text) IS NULL AND c.tache_id IS NULL OR c.tache_id::text = :tache) "
    "ORDER BY c.cree_le"
)


async def _charger_commentaire_edition(
    session: AsyncSession, courant: dict[str, Any], commentaire_id: int
) -> str:
    """Vérifie que le commentaire existe et appartient à l'auteur connecté ; renvoie activite_id."""
    ligne = (
        await session.execute(
            text("SELECT activite_id::text AS aid, auteur_id::text AS auteur FROM core.commentaire "
                 "WHERE id = :id"),
            {"id": commentaire_id},
        )
    ).mappings().first()
    if ligne is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Commentaire introuvable."
        )
    if ligne["auteur"] != courant["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul l'auteur peut modifier ou supprimer ce commentaire.",
        )
    return str(ligne["aid"])


async def _exiger_tache_de_l_activite(
    session: AsyncSession, activite_id: str, tache_id: str | None
) -> str | None:
    """Vérifie que la tâche appartient bien à l'activité ; renvoie son titre (ou None)."""
    if tache_id is None:
        return None
    titre = await session.scalar(
        text(
            "SELECT titre FROM core.tache "
            "WHERE id::text = :tid AND activite_id = cast(:aid as uuid)"
        ),
        {"tid": tache_id, "aid": activite_id},
    )
    if titre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable sur cette activité."
        )
    return str(titre)


async def _exiger_equipement(session: AsyncSession, equipement_id: str) -> str:
    """L'équipement existe ? Renvoie sa désignation, pour les libellés d'audit et de notification.

    Pas de cloisonnement par direction ici : le parc est un référentiel partagé, visible par tous
    ceux qui ont l'accès au module (garde `exiger_acces` sur le routeur inventaire).
    """
    ligne = (
        await session.execute(
            text(
                "SELECT coalesce(code_immo, designation) AS repere, designation, "
                "detenteur_id::text AS detenteur FROM core.equipement WHERE id = cast(:i as uuid)"
            ),
            {"i": equipement_id},
        )
    ).mappings().first()
    if ligne is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Équipement introuvable.")
    return str(ligne["repere"])


@routeur.get("/equipement/{equipement_id}", response_model=list[CommentaireItem])
async def lister_equipement(
    equipement_id: str, courant: Courant, session: Session
) -> list[dict[str, Any]]:
    """Fil de discussion d'un équipement — même mécanique que celui d'une activité."""
    await _exiger_equipement(session, equipement_id)
    lignes = (
        await session.execute(_LISTE_EQUIPEMENT, {"id": equipement_id, "moi": courant["id"]})
    ).mappings().all()
    messages: list[dict[str, Any]] = [dict(x) for x in lignes]
    for m in messages:
        # Les images restent réservées aux activités : rien ne les dépose sur un équipement.
        m["images"] = []
    return messages


@routeur.post(
    "/equipement/{equipement_id}",
    response_model=CommentaireItem,
    status_code=status.HTTP_201_CREATED,
)
async def commenter_equipement(
    equipement_id: str, corps: CommentaireCreation, courant: Courant, session: Session
) -> dict[str, Any]:
    repere = await _exiger_equipement(session, equipement_id)
    texte_msg = corps.texte.strip()
    ligne = (
        await session.execute(
            text(
                "INSERT INTO core.commentaire (equipement_id, auteur_id, auteur_email, texte) "
                "VALUES (cast(:eid as uuid), cast(:uid as uuid), :email, :texte) "
                "RETURNING id, texte, cree_le"
            ),
            {
                "eid": equipement_id,
                "uid": courant["id"],
                "email": courant["email"],
                "texte": texte_msg,
            },
        )
    ).mappings().one()
    # Mentions @ : mêmes règles qu'ailleurs. Pas de notification « aux acteurs » — un équipement
    # n'en a pas ; seul son détenteur pourrait l'être, et il n'a pas demandé à suivre le fil.
    for uid in {m for m in corps.mentions if m and m != courant["id"]}:
        await notifier(
            session,
            destinataire_id=uid,
            activite_id=None,
            type_="MENTION",
            titre=f"Vous êtes mentionné — {repere}",
            message=f"{courant['email']} vous a mentionné : {texte_msg[:140]}",
        )
    await audit.consigner(
        session,
        action="COMMENTAIRE",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        module="inventaire",
        cible_type="equipement",
        cible_id=repere,
    )
    await session.commit()
    return {
        "id": ligne["id"],
        "texte": ligne["texte"],
        "cree_le": ligne["cree_le"],
        "auteur_id": courant["id"],
        "edite": False,
        "auteur": f"{courant['prenom']} {courant['nom']}"
        if courant.get("prenom")
        else courant["email"],
    }


@routeur.get("/{activite_id}/export")
async def exporter_discussion(
    activite_id: str,
    courant: Courant,
    session: Session,
    format: Annotated[str, Query(alias="format")] = "csv",
) -> Response:
    """Exporte la discussion interne d'une activité (activité + tâches) en CSV ou Excel."""
    reference = await _exiger_activite_visible(session, courant, activite_id)
    lignes = (
        await session.execute(
            text(
                "SELECT c.cree_le, "
                "coalesce(u.prenom || ' ' || u.nom, c.auteur_email) AS auteur, "
                "c.texte, t.titre AS tache "
                "FROM core.commentaire c LEFT JOIN core.utilisateur u ON u.id = c.auteur_id "
                "LEFT JOIN core.tache t ON t.id = c.tache_id "
                "WHERE c.activite_id = cast(:id as uuid) ORDER BY c.cree_le"
            ),
            {"id": activite_id},
        )
    ).mappings().all()
    entetes = ["Date", "Auteur", "Rattaché à", "Message"]
    donnees = [
        [
            r["cree_le"].strftime("%Y-%m-%d %H:%M"),
            r["auteur"],
            r["tache"] or "Discussion générale",
            r["texte"],
        ]
        for r in lignes
    ]
    nom = f"discussion-{reference}"
    if format == "xlsx":
        contenu = vers_xlsx(entetes, donnees, "Discussion")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:
        contenu = vers_csv(entetes, donnees)
        media = "text/csv"
        ext = "csv"
    return Response(
        content=contenu,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename={nom}.{ext}"},
    )


@routeur.get("/{activite_id}", response_model=list[CommentaireItem])
async def lister(
    activite_id: str,
    courant: Courant,
    session: Session,
    tache: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    await _exiger_activite_visible(session, courant, activite_id)
    await _exiger_tache_de_l_activite(session, activite_id, tache)
    lignes = (
        await session.execute(
            _LISTE, {"id": activite_id, "tache": tache, "moi": courant["id"]}
        )
    ).mappings().all()
    messages: list[dict[str, Any]] = [dict(x) for x in lignes]
    if not messages:
        return messages
    # Une seule requête pour toutes les images du fil (pas de N+1).
    images = (
        await session.execute(
            _IMAGES_DU_FIL, {"ids": [int(m["id"]) for m in messages]}
        )
    ).mappings().all()
    par_message: dict[int, list[dict[str, Any]]] = {}
    for img in images:
        par_message.setdefault(int(img["commentaire_id"]), []).append(
            {
                "id": img["id"],
                "nom": img["nom"],
                "type_mime": img["type_mime"],
                "largeur": img["largeur"],
                "hauteur": img["hauteur"],
            }
        )
    for m in messages:
        m["images"] = par_message.get(int(m["id"]), [])
    return messages


@routeur.post("/{activite_id}/vues", status_code=status.HTTP_204_NO_CONTENT)
async def marquer_vues(
    activite_id: str,
    courant: Courant,
    session: Session,
    tache: Annotated[str | None, Query()] = None,
) -> None:
    """Marque comme lus, par l'utilisateur connecté, tous les messages du fil (hors les siens)."""
    await _exiger_activite_visible(session, courant, activite_id)
    await _exiger_tache_de_l_activite(session, activite_id, tache)
    await session.execute(
        text(
            "INSERT INTO core.commentaire_vue (commentaire_id, utilisateur_id) "
            "SELECT c.id, cast(:moi as uuid) FROM core.commentaire c "
            "WHERE c.activite_id = cast(:id as uuid) "
            "AND (cast(:tache as text) IS NULL AND c.tache_id IS NULL "
            "     OR c.tache_id::text = :tache) "
            "AND (c.auteur_id IS DISTINCT FROM cast(:moi as uuid)) "
            "ON CONFLICT DO NOTHING"
        ),
        {"id": activite_id, "tache": tache, "moi": courant["id"]},
    )
    await session.commit()


@routeur.get("/msg/{commentaire_id}/vues", response_model=list[LecteurCommentaire])
async def lecteurs(
    commentaire_id: int, courant: Courant, session: Session
) -> list[dict[str, Any]]:
    """Liste des personnes ayant vu un commentaire (accusés de lecture), plus récent d'abord."""
    aid = await session.scalar(
        text("SELECT activite_id::text FROM core.commentaire WHERE id = :id"),
        {"id": commentaire_id},
    )
    if aid is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Commentaire introuvable."
        )
    await _exiger_activite_visible(session, courant, str(aid))
    lignes = (
        await session.execute(
            text(
                "SELECT (u.prenom || ' ' || u.nom) AS nom, v.vu_le "
                "FROM core.commentaire_vue v JOIN core.utilisateur u ON u.id = v.utilisateur_id "
                "WHERE v.commentaire_id = :id ORDER BY v.vu_le DESC"
            ),
            {"id": commentaire_id},
        )
    ).mappings().all()
    return [dict(x) for x in lignes]


async def _enregistrer_commentaire(
    session: AsyncSession,
    *,
    activite_id: str,
    tache: str | None,
    texte: str,
    mentions: list[str],
    courant: dict[str, Any],
) -> dict[str, Any]:
    """Insère le message, notifie mentions et acteurs, journalise. Ne committe pas.

    Partagé par le dépôt d'un message texte et par celui d'un message avec images.
    """
    reference = await _exiger_activite_visible(session, courant, activite_id)
    titre_tache = await _exiger_tache_de_l_activite(session, activite_id, tache)
    ligne = (
        await session.execute(
            text(
                "INSERT INTO core.commentaire (activite_id, tache_id, auteur_id, auteur_email, "
                "texte) VALUES (cast(:aid as uuid), cast(:tid as uuid), cast(:uid as uuid), "
                ":email, :texte) RETURNING id, texte, cree_le"
            ),
            {
                "aid": activite_id,
                "tid": tache,
                "uid": courant["id"],
                "email": courant["email"],
                "texte": texte,
            },
        )
    ).mappings().one()
    cible = f"{reference} · {titre_tache}" if titre_tache else reference
    # Mentions @ : les personnes citées sont prévenues (cloche + e-mail selon leur préférence),
    # sauf l'auteur — on ne se notifie pas soi-même.
    for uid in {m for m in mentions if m and m != courant["id"]}:
        await notifier(
            session,
            destinataire_id=uid,
            activite_id=activite_id,
            type_="MENTION",
            titre=f"Vous êtes mentionné — {cible}",
            message=f"{courant['email']} vous a mentionné : {texte[:140]}",
        )
    await audit.consigner(
        session,
        action="COMMENTAIRE",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        cible_type="tache" if titre_tache else "activite",
        cible_id=cible,
    )
    await notifier_acteurs(
        session,
        activite_id=activite_id,
        type_="COMMENTAIRE",
        titre=f"Nouveau commentaire — {cible}",
        message=(
            f"{courant['email']} a commenté la tâche « {titre_tache} » de {reference}."
            if titre_tache
            else f"{courant['email']} a commenté l'activité {reference}."
        ),
        exclure_id=courant["id"],
    )
    return {
        "id": ligne["id"],
        "texte": ligne["texte"],
        "cree_le": ligne["cree_le"],
        "auteur_id": courant["id"],
        "edite": False,
        "auteur": f"{courant['prenom']} {courant['nom']}"
        if courant.get("prenom")
        else courant["email"],
    }


@routeur.post("/{activite_id}", response_model=CommentaireItem, status_code=status.HTTP_201_CREATED)
async def commenter(
    activite_id: str,
    corps: CommentaireCreation,
    courant: Courant,
    session: Session,
    tache: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    item = await _enregistrer_commentaire(
        session,
        activite_id=activite_id,
        tache=tache,
        texte=corps.texte.strip(),
        mentions=corps.mentions,
        courant=courant,
    )
    await session.commit()
    return item


@routeur.post(
    "/{activite_id}/images",
    response_model=CommentaireItem,
    status_code=status.HTTP_201_CREATED,
)
async def commenter_avec_images(
    activite_id: str,
    courant: Courant,
    session: Session,
    fichiers: Annotated[list[UploadFile], File()],
    texte: Annotated[str, Form()] = "",
    mentions: Annotated[str, Form()] = "",
    tache: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Dépose un message accompagné d'images (captures d'écran).

    Message et images sont écrits dans la même transaction : jamais d'image orpheline ni de
    message amputé. `mentions` : identifiants séparés par des virgules (le multipart ne
    transporte pas de JSON).
    """
    images = [f for f in fichiers if f.filename]
    if not images:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Aucune image fournie."
        )
    if len(images) > _MAX_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{_MAX_IMAGES} images au maximum par message.",
        )
    valides = [await _lire_image_valide(f) for f in images]

    item = await _enregistrer_commentaire(
        session,
        activite_id=activite_id,
        tache=tache,
        texte=texte.strip(),
        mentions=[m for m in mentions.split(",") if m],
        courant=courant,
    )
    for nom, contenu, type_mime, largeur, hauteur in valides:
        await session.execute(
            text(
                "INSERT INTO core.commentaire_image "
                "(commentaire_id, nom, type_mime, taille, largeur, hauteur, contenu) "
                "VALUES (:cid, :nom, :mime, :taille, :l, :h, :contenu)"
            ),
            {
                "cid": item["id"],
                "nom": nom,
                "mime": type_mime,
                "taille": len(contenu),
                "l": largeur,
                "h": hauteur,
                "contenu": contenu,
            },
        )
    await session.commit()
    item["images"] = await _images_du_commentaire(session, int(item["id"]))
    return item


@routeur.get("/msg/{commentaire_id}/images/{image_id}")
async def image(
    commentaire_id: int, image_id: str, courant: Courant, session: Session
) -> Response:
    """Renvoie les octets d'une image du fil, après contrôle de périmètre sur l'activité."""
    ligne = (
        await session.execute(
            text(
                "SELECT i.contenu, i.type_mime, c.activite_id::text AS aid "
                "FROM core.commentaire_image i JOIN core.commentaire c ON c.id = i.commentaire_id "
                "WHERE i.id = cast(:id as uuid) AND i.commentaire_id = :cid"
            ),
            {"id": image_id, "cid": commentaire_id},
        )
    ).mappings().first()
    if ligne is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image introuvable.")
    await _exiger_activite_visible(session, courant, ligne["aid"])
    return Response(
        content=ligne["contenu"],
        media_type=ligne["type_mime"],
        # Le type vient du décodage réel au dépôt : on interdit au navigateur de le deviner.
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"},
    )


@routeur.patch("/msg/{commentaire_id}", response_model=CommentaireItem)
async def modifier(
    commentaire_id: int, corps: CommentaireMaj, courant: Courant, session: Session
) -> dict[str, Any]:
    """Modifie son propre commentaire (marqué « modifié »)."""
    await _charger_commentaire_edition(session, courant, commentaire_id)
    ligne = (
        await session.execute(
            text(
                "UPDATE core.commentaire SET texte = :texte, maj_le = now() "
                "WHERE id = :id RETURNING id, texte, cree_le, auteur_id::text AS auteur_id"
            ),
            {"id": commentaire_id, "texte": corps.texte.strip()},
        )
    ).mappings().one()
    await session.commit()
    return {
        "id": ligne["id"],
        "texte": ligne["texte"],
        "cree_le": ligne["cree_le"],
        "auteur_id": ligne["auteur_id"],
        "edite": True,
        "auteur": f"{courant['prenom']} {courant['nom']}"
        if courant.get("prenom")
        else courant["email"],
    }


@routeur.delete("/msg/{commentaire_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer(commentaire_id: int, courant: Courant, session: Session) -> None:
    """Supprime son propre commentaire."""
    await _charger_commentaire_edition(session, courant, commentaire_id)
    await session.execute(
        text("DELETE FROM core.commentaire WHERE id = :id"), {"id": commentaire_id}
    )
    await session.commit()

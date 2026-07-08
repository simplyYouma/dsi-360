"""Fil de discussion interne DSI rattaché à une activité (tous modules).

Le demandeur n'a pas accès à la plateforme : ces échanges sont internes. Cloisonnement
par direction (un non-transverse ne commente que les activités de son périmètre).

Chaque **tâche** a aussi son propre fil (paramètre ``tache``) : le fil de l'activité n'affiche
que les commentaires sans tâche, celui d'une tâche uniquement les siens.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.application.notifications import notifier_acteurs
from dsi360.infrastructure import audit
from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import CommentaireCreation, CommentaireItem
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/commentaires", tags=["commentaires"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]


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
    if not courant["transverse"] and ligne["direction"] not in (None, courant["direction"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hors périmètre.")
    return str(ligne["reference"])


_LISTE = text(
    "SELECT c.id, c.texte, c.cree_le, "
    "coalesce(u.prenom || ' ' || u.nom, c.auteur_email) AS auteur "
    "FROM core.commentaire c LEFT JOIN core.utilisateur u ON u.id = c.auteur_id "
    "WHERE c.activite_id = cast(:id as uuid) "
    "AND (cast(:tache as text) IS NULL AND c.tache_id IS NULL OR c.tache_id::text = :tache) "
    "ORDER BY c.cree_le"
)


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
        await session.execute(_LISTE, {"id": activite_id, "tache": tache})
    ).mappings().all()
    return [dict(x) for x in lignes]


@routeur.post("/{activite_id}", response_model=CommentaireItem, status_code=status.HTTP_201_CREATED)
async def commenter(
    activite_id: str,
    corps: CommentaireCreation,
    courant: Courant,
    session: Session,
    tache: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
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
                "texte": corps.texte.strip(),
            },
        )
    ).mappings().one()
    cible = f"{reference} · {titre_tache}" if titre_tache else reference
    # Mentions @ : notification interne (cloche) aux personnes citées, sauf l'auteur. L'envoi
    # d'e-mail automatique de ces mentions sera branché ultérieurement.
    for uid in {m for m in corps.mentions if m and m != courant["id"]}:
        await session.execute(
            text(
                "INSERT INTO core.notification "
                "(destinataire_id, activite_id, type, titre, message) "
                "SELECT cast(:dest as uuid), cast(:aid as uuid), 'MENTION', :titre, :msg "
                "WHERE EXISTS (SELECT 1 FROM core.utilisateur WHERE id = cast(:dest as uuid) "
                "              AND actif)"
            ),
            {
                "dest": uid,
                "aid": activite_id,
                "titre": f"Vous êtes mentionné — {cible}",
                "msg": f"{courant['email']} vous a mentionné : {corps.texte.strip()[:140]}",
            },
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
    await session.commit()
    return {
        "id": ligne["id"],
        "texte": ligne["texte"],
        "cree_le": ligne["cree_le"],
        "auteur": f"{courant['prenom']} {courant['nom']}"
        if courant.get("prenom")
        else courant["email"],
    }

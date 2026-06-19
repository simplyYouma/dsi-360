"""Fil de discussion interne DSI rattaché à une activité (tous modules).

Le demandeur n'a pas accès à la plateforme : ces échanges sont internes. Cloisonnement
par direction (un non-transverse ne commente que les activités de son périmètre).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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
    "WHERE c.activite_id = cast(:id as uuid) ORDER BY c.cree_le"
)


@routeur.get("/{activite_id}", response_model=list[CommentaireItem])
async def lister(activite_id: str, courant: Courant, session: Session) -> list[dict[str, Any]]:
    await _exiger_activite_visible(session, courant, activite_id)
    lignes = (await session.execute(_LISTE, {"id": activite_id})).mappings().all()
    return [dict(x) for x in lignes]


@routeur.post("/{activite_id}", response_model=CommentaireItem, status_code=status.HTTP_201_CREATED)
async def commenter(
    activite_id: str, corps: CommentaireCreation, courant: Courant, session: Session
) -> dict[str, Any]:
    reference = await _exiger_activite_visible(session, courant, activite_id)
    ligne = (
        await session.execute(
            text(
                "INSERT INTO core.commentaire (activite_id, auteur_id, auteur_email, texte) "
                "VALUES (cast(:aid as uuid), cast(:uid as uuid), :email, :texte) "
                "RETURNING id, texte, cree_le"
            ),
            {
                "aid": activite_id,
                "uid": courant["id"],
                "email": courant["email"],
                "texte": corps.texte.strip(),
            },
        )
    ).mappings().one()
    await audit.consigner(
        session,
        action="COMMENTAIRE",
        acteur_id=courant["id"],
        acteur_email=courant["email"],
        cible_type="activite",
        cible_id=reference,
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

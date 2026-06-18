"""Référentiel des demandeurs (agents de la banque qui remontent incidents/demandes).

CRUD réservé aux profils transverses. Les demandeurs sont aussi créés automatiquement à
l'import et reconnus d'une fois sur l'autre (nom normalisé unique).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.infrastructure.db import session_scope
from dsi360.interface.schemas import (
    DemandeurCreation,
    DemandeurMaj,
    PageDemandeurs,
)
from dsi360.interface.securite import utilisateur_courant

routeur = APIRouter(prefix="/demandeurs", tags=["demandeurs"])
Session = Annotated[AsyncSession, Depends(session_scope)]
Courant = Annotated[dict[str, Any], Depends(utilisateur_courant)]
_TAILLE = 15


def _exiger_transverse(courant: dict[str, Any]) -> None:
    if not courant["transverse"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé.")


async def _direction_id(session: AsyncSession, code: str | None) -> str | None:
    if code is None:
        return None
    ident = await session.scalar(
        text("SELECT id::text FROM core.direction WHERE code = :c"), {"c": code}
    )
    if ident is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Direction inconnue.")
    return str(ident)


_LISTE = text(
    "SELECT d.id::text AS id, d.nom_complet, dir.libelle AS direction, d.email, d.actif "
    "FROM core.demandeur d LEFT JOIN core.direction dir ON dir.id = d.direction_id "
    "WHERE (:q = '' OR d.nom_complet ILIKE :motif) "
    "ORDER BY d.nom_complet LIMIT :limite OFFSET :decalage"
)


@routeur.get("", response_model=PageDemandeurs)
async def lister(
    courant: Courant,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    q: Annotated[str, Query(max_length=80)] = "",
) -> dict[str, Any]:
    _exiger_transverse(courant)
    terme = q.strip()
    params = {
        "q": terme,
        "motif": f"%{terme}%",
        "limite": _TAILLE,
        "decalage": (page - 1) * _TAILLE,
    }
    total = await session.scalar(
        text("SELECT count(*) FROM core.demandeur WHERE (:q = '' OR nom_complet ILIKE :motif)"),
        {"q": terme, "motif": f"%{terme}%"},
    ) or 0
    lignes = (await session.execute(_LISTE, params)).mappings().all()
    return {"elements": [dict(x) for x in lignes], "total": total, "page": page, "taille": _TAILLE}


@routeur.post("", status_code=status.HTTP_201_CREATED)
async def creer(corps: DemandeurCreation, courant: Courant, session: Session) -> dict[str, str]:
    _exiger_transverse(courant)
    direction_id = await _direction_id(session, corps.direction_code)
    ident = await session.scalar(
        text(
            "INSERT INTO core.demandeur (nom_complet, direction_id, email) "
            "VALUES (:nom, cast(:dir as uuid), :email) "
            "ON CONFLICT (lower(nom_complet)) DO NOTHING RETURNING id::text"
        ),
        {"nom": corps.nom_complet.strip(), "dir": direction_id, "email": corps.email},
    )
    if ident is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Demandeur déjà existant.")
    await session.commit()
    return {"id": str(ident)}


@routeur.put("/{ident}", status_code=status.HTTP_204_NO_CONTENT)
async def modifier(ident: str, corps: DemandeurMaj, courant: Courant, session: Session) -> None:
    _exiger_transverse(courant)
    direction_id = await _direction_id(session, corps.direction_code)
    touche = await session.scalar(
        text(
            "UPDATE core.demandeur SET nom_complet = :nom, direction_id = cast(:dir as uuid), "
            "email = :email, actif = :actif, maj_le = now() "
            "WHERE id = cast(:id as uuid) RETURNING id::text"
        ),
        {
            "id": ident,
            "nom": corps.nom_complet.strip(),
            "dir": direction_id,
            "email": corps.email,
            "actif": corps.actif,
        },
    )
    if touche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demandeur introuvable.")
    await session.commit()


@routeur.delete("/{ident}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer(ident: str, courant: Courant, session: Session) -> None:
    _exiger_transverse(courant)
    # Refus si le demandeur est référencé par des activités (zéro perte de cohérence).
    lie = await session.scalar(
        text("SELECT 1 FROM core.activite WHERE demandeur_externe_id = cast(:id as uuid) LIMIT 1"),
        {"id": ident},
    )
    if lie is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Demandeur rattaché à des tickets : désactivez-le plutôt que de le supprimer.",
        )
    touche = await session.scalar(
        text("DELETE FROM core.demandeur WHERE id = cast(:id as uuid) RETURNING id::text"),
        {"id": ident},
    )
    if touche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demandeur introuvable.")
    await session.commit()

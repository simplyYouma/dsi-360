"""Sélection d'un gestionnaire par niveau de support pour l'escalade.

Le niveau (N1/N2/N3) est une propriété du gestionnaire (``core.utilisateur.niveau_support``), fixée
à la création/édition du compte. À l'escalade, on réaffecte le ticket au gestionnaire du niveau
cible le moins chargé, dans la direction du ticket si possible.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def membre_le_moins_charge(
    session: AsyncSession, niveau: int, direction: str | None
) -> str | None:
    """Gestionnaire actif de ce niveau ayant le moins d'activités en cours, ou ``None``.

    ``direction`` = code de la direction du ticket ; ``None`` accepte n'importe quelle direction.
    On privilégie la direction du ticket, puis on élargit si aucun gestionnaire n'y répond.
    """
    requete = text(
        "SELECT u.id::text FROM core.utilisateur u "
        "LEFT JOIN core.direction d ON d.id = u.direction_id "
        "WHERE u.actif AND u.niveau_support = :n "
        "  AND (cast(:d as text) IS NULL OR d.code = :d) "
        "ORDER BY (SELECT count(*) FROM core.activite a "
        "          WHERE a.responsable_id = u.id "
        "          AND a.cloture_le IS NULL AND a.resolu_le IS NULL) ASC, u.cree_le ASC "
        "LIMIT 1"
    )
    uid = await session.scalar(requete, {"n": niveau, "d": direction})
    if uid is None and direction is not None:
        # Aucun gestionnaire de ce niveau dans la direction : on élargit à toutes les directions.
        uid = await session.scalar(requete, {"n": niveau, "d": None})
    return str(uid) if uid is not None else None

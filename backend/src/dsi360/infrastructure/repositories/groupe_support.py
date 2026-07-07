"""Repository des groupes de support ITIL (N1/N2/N3), propres à chaque direction.

DSI : N1/N2/N3 ; DBS : N3 uniquement. L'escalade fonctionnelle réaffecte le ticket au membre le
moins chargé du groupe (direction du ticket, niveau cible) ; l'appelant monte jusqu'au N3 si le
niveau demandé n'existe pas ou n'a aucun membre dans cette direction.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def lister(session: AsyncSession) -> list[dict[str, Any]]:
    """Tous les groupes (direction + niveau) avec leurs membres (pour l'administration)."""
    groupes = (
        await session.execute(
            text(
                "SELECT g.id::text AS id, g.niveau, g.nom, d.code AS direction, "
                "       d.libelle AS direction_libelle "
                "FROM core.groupe_support g JOIN core.direction d ON d.id = g.direction_id "
                "ORDER BY d.code, g.niveau"
            )
        )
    ).mappings().all()
    membres = (
        await session.execute(
            text(
                "SELECT gsm.groupe_id::text AS gid, u.id::text AS id, u.prenom, u.nom, u.email "
                "FROM core.groupe_support_membre gsm "
                "JOIN core.utilisateur u ON u.id = gsm.utilisateur_id "
                "ORDER BY u.prenom, u.nom"
            )
        )
    ).mappings().all()
    par_groupe: dict[str, list[dict[str, Any]]] = {}
    for m in membres:
        par_groupe.setdefault(m["gid"], []).append(
            {"id": m["id"], "prenom": m["prenom"], "nom": m["nom"], "email": m["email"]}
        )
    return [
        {
            "direction": g["direction"],
            "direction_libelle": g["direction_libelle"],
            "niveau": g["niveau"],
            "nom": g["nom"],
            "membres": par_groupe.get(g["id"], []),
        }
        for g in groupes
    ]


async def definir_membres(
    session: AsyncSession, direction: str, niveau: int, utilisateur_ids: list[str]
) -> bool:
    """Remplace les membres du groupe (direction, niveau). False si le groupe n'existe pas."""
    gid = await session.scalar(
        text(
            "SELECT g.id::text FROM core.groupe_support g "
            "JOIN core.direction d ON d.id = g.direction_id "
            "WHERE d.code = :d AND g.niveau = :n"
        ),
        {"d": direction, "n": niveau},
    )
    if gid is None:
        return False
    await session.execute(
        text("DELETE FROM core.groupe_support_membre WHERE groupe_id = cast(:g as uuid)"),
        {"g": gid},
    )
    for uid in utilisateur_ids:
        await session.execute(
            text(
                "INSERT INTO core.groupe_support_membre (groupe_id, utilisateur_id) "
                "VALUES (cast(:g as uuid), cast(:u as uuid)) ON CONFLICT DO NOTHING"
            ),
            {"g": gid, "u": uid},
        )
    return True


async def membre_le_moins_charge(
    session: AsyncSession, niveau: int, direction: str | None
) -> str | None:
    """Membre actif le moins chargé du groupe (direction, niveau), ou ``None``.

    ``direction`` = code de la direction du ticket ; ``None`` (ticket sans direction) accepte le
    groupe du niveau de n'importe quelle direction. Permet une réaffectation équilibrée.
    """
    uid = await session.scalar(
        text(
            "SELECT m.utilisateur_id::text FROM core.groupe_support g "
            "JOIN core.direction d ON d.id = g.direction_id "
            "JOIN core.groupe_support_membre m ON m.groupe_id = g.id "
            "JOIN core.utilisateur u ON u.id = m.utilisateur_id AND u.actif "
            "WHERE g.niveau = :n AND (cast(:d as text) IS NULL OR d.code = :d) "
            "ORDER BY (SELECT count(*) FROM core.activite a "
            "          WHERE a.responsable_id = m.utilisateur_id "
            "          AND a.cloture_le IS NULL AND a.resolu_le IS NULL) ASC, u.cree_le ASC "
            "LIMIT 1"
        ),
        {"n": niveau, "d": direction},
    )
    return str(uid) if uid is not None else None

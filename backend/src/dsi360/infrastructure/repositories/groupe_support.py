"""Repository des groupes de support ITIL (N1/N2/N3) et de leurs membres.

L'escalade fonctionnelle réaffecte le ticket au membre le moins chargé du groupe du niveau cible.
Groupes paramétrables (un par niveau) ; les membres sont gérés depuis l'administration.
"""

from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession


async def lister(session: AsyncSession) -> list[dict[str, Any]]:
    """Les 3 groupes avec leurs membres (pour l'administration)."""
    groupes = (
        await session.execute(
            text("SELECT id::text AS id, niveau, nom FROM core.groupe_support ORDER BY niveau")
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
        {"niveau": g["niveau"], "nom": g["nom"], "membres": par_groupe.get(g["id"], [])}
        for g in groupes
    ]


async def definir_membres(
    session: AsyncSession, niveau: int, utilisateur_ids: list[str]
) -> bool:
    """Remplace les membres du groupe d'un niveau. False si le niveau n'existe pas."""
    gid = await session.scalar(
        text("SELECT id::text FROM core.groupe_support WHERE niveau = :n"), {"n": niveau}
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


async def membre_le_moins_charge(session: AsyncSession, niveau: int) -> str | None:
    """Membre actif du groupe du niveau ayant le moins d'activités en cours, ou ``None``.

    Permet une réaffectation équilibrée à l'escalade. ``None`` si le groupe est vide/non configuré.
    """
    uid = await session.scalar(
        text(
            "SELECT m.utilisateur_id::text FROM core.groupe_support g "
            "JOIN core.groupe_support_membre m ON m.groupe_id = g.id "
            "JOIN core.utilisateur u ON u.id = m.utilisateur_id AND u.actif "
            "WHERE g.niveau = :n "
            "ORDER BY (SELECT count(*) FROM core.activite a "
            "          WHERE a.responsable_id = m.utilisateur_id "
            "          AND a.cloture_le IS NULL AND a.resolu_le IS NULL) ASC, u.cree_le ASC "
            "LIMIT 1"
        ),
        {"n": niveau},
    )
    return str(uid) if uid is not None else None


async def par_niveau(session: AsyncSession, niveau: int) -> RowMapping | None:
    return (
        await session.execute(
            text("SELECT id::text AS id, niveau, nom FROM core.groupe_support WHERE niveau = :n"),
            {"n": niveau},
        )
    ).mappings().first()

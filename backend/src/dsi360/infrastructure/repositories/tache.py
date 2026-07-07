"""Repository des tâches (core.tache), rattachées à une activité (projet, changement…)."""

from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

_CHAMPS = """
    t.id::text AS id, t.activite_id::text AS activite_id, t.titre, t.description, t.statut,
    t.assigne_id::text AS assigne_id, t.echeance, t.ordre, t.cree_le, t.maj_le,
    u.prenom AS assigne_prenom, u.nom AS assigne_nom, u.email AS assigne_email,
    (SELECT count(*) FROM core.commentaire c WHERE c.tache_id = t.id) AS nb_commentaires
"""

_BASE = """
    FROM core.tache t
    LEFT JOIN core.utilisateur u ON u.id = t.assigne_id
"""

# Champs modifiables via maj() (liste blanche : jamais d'injection de colonne).
_MODIFIABLES = frozenset({"titre", "description", "statut", "assigne_id", "echeance", "ordre"})


async def lister(session: AsyncSession, activite_id: str) -> list[RowMapping]:
    lignes = await session.execute(
        text(
            f"SELECT {_CHAMPS} {_BASE} WHERE t.activite_id = cast(:a as uuid) "
            "ORDER BY t.ordre, t.cree_le"
        ),
        {"a": activite_id},
    )
    return list(lignes.mappings().all())


async def lister_pour_utilisateur(
    session: AsyncSession, utilisateur_id: str, *, inclure_terminees: bool = False
) -> list[RowMapping]:
    """Tâches assignées à un utilisateur, avec leur activité parente (pour la navigation)."""
    filtre_statut = "" if inclure_terminees else "AND t.statut <> 'Terminée' "
    lignes = await session.execute(
        text(
            "SELECT t.id::text AS id, t.titre, t.statut, t.echeance, t.cree_le, "
            "       a.id::text AS activite_id, a.module, a.reference, a.titre AS activite_titre "
            "FROM core.tache t JOIN core.activite a ON a.id = t.activite_id "
            "WHERE t.assigne_id = cast(:u as uuid) "
            f"{filtre_statut}"
            "ORDER BY (t.echeance IS NULL), t.echeance, t.cree_le"
        ),
        {"u": utilisateur_id},
    )
    return list(lignes.mappings().all())


async def par_id(session: AsyncSession, tache_id: str) -> RowMapping | None:
    resultat = await session.execute(
        text(f"SELECT {_CHAMPS} {_BASE} WHERE t.id = cast(:id as uuid)"), {"id": tache_id}
    )
    return resultat.mappings().first()


async def creer(session: AsyncSession, activite_id: str, champs: dict[str, Any]) -> str:
    params = {
        "a": activite_id,
        "titre": champs["titre"],
        "description": champs.get("description"),
        "assigne_id": champs.get("assigne_id"),
        "echeance": champs.get("echeance"),
        "ordre": champs.get("ordre", 0),
    }
    identifiant = await session.scalar(
        text(
            "INSERT INTO core.tache (activite_id, titre, description, assigne_id, echeance, ordre) "
            "VALUES (cast(:a as uuid), :titre, :description, cast(:assigne_id as uuid), "
            " :echeance, :ordre) RETURNING id::text"
        ),
        params,
    )
    return str(identifiant)


async def maj(session: AsyncSession, tache_id: str, champs: dict[str, Any]) -> None:
    fixes = {c: v for c, v in champs.items() if c in _MODIFIABLES}
    if not fixes:
        return
    fragments = []
    for colonne in fixes:
        if colonne == "assigne_id":
            fragments.append("assigne_id = cast(:assigne_id as uuid)")
        else:
            fragments.append(f"{colonne} = :{colonne}")
    params: dict[str, Any] = {"id": tache_id, **fixes}
    await session.execute(
        text(
            f"UPDATE core.tache SET {', '.join(fragments)}, maj_le = now() "
            "WHERE id = cast(:id as uuid)"
        ),
        params,
    )


async def supprimer(session: AsyncSession, tache_id: str) -> None:
    await session.execute(
        text("DELETE FROM core.tache WHERE id = cast(:id as uuid)"), {"id": tache_id}
    )


async def compter(session: AsyncSession, activite_id: str) -> tuple[int, int]:
    """(total, terminées) des tâches d'une activité — base du calcul d'avancement."""
    ligne = (
        await session.execute(
            text(
                "SELECT count(*) AS total, "
                "count(*) FILTER (WHERE statut = 'Terminée') AS terminees "
                "FROM core.tache WHERE activite_id = cast(:a as uuid)"
            ),
            {"a": activite_id},
        )
    ).mappings().one()
    return int(ligne["total"]), int(ligne["terminees"])

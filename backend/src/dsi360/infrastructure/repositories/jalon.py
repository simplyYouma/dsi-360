"""Repository des jalons de projet (core.jalon) — dates clés d'une activité."""

from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

_CHAMPS = "id::text AS id, titre, echeance, atteint, ordre"
_MODIFIABLES = frozenset({"titre", "echeance", "atteint", "ordre"})


async def lister(session: AsyncSession, activite_id: str) -> list[RowMapping]:
    lignes = await session.execute(
        text(
            f"SELECT {_CHAMPS} FROM core.jalon WHERE activite_id = cast(:a as uuid) "
            "ORDER BY ordre, echeance NULLS LAST, cree_le"
        ),
        {"a": activite_id},
    )
    return list(lignes.mappings().all())


async def par_id(session: AsyncSession, jalon_id: str, activite_id: str) -> RowMapping | None:
    resultat = await session.execute(
        text(
            f"SELECT {_CHAMPS} FROM core.jalon "
            "WHERE id = cast(:id as uuid) AND activite_id = cast(:a as uuid)"
        ),
        {"id": jalon_id, "a": activite_id},
    )
    return resultat.mappings().first()


async def creer(session: AsyncSession, activite_id: str, champs: dict[str, Any]) -> RowMapping:
    ligne = (
        await session.execute(
            text(
                "INSERT INTO core.jalon (activite_id, titre, echeance, ordre) "
                "VALUES (cast(:a as uuid), :titre, :echeance, :ordre) "
                f"RETURNING {_CHAMPS}"
            ),
            {
                "a": activite_id,
                "titre": champs["titre"],
                "echeance": champs.get("echeance"),
                "ordre": champs.get("ordre", 0),
            },
        )
    ).mappings().one()
    return ligne


async def maj(session: AsyncSession, jalon_id: str, champs: dict[str, Any]) -> None:
    fixes = {c: v for c, v in champs.items() if c in _MODIFIABLES}
    if not fixes:
        return
    fragments = ", ".join(f"{c} = :{c}" for c in fixes)
    await session.execute(
        text(f"UPDATE core.jalon SET {fragments} WHERE id = cast(:id as uuid)"),
        {"id": jalon_id, **fixes},
    )


async def supprimer(session: AsyncSession, jalon_id: str) -> None:
    await session.execute(
        text("DELETE FROM core.jalon WHERE id = cast(:id as uuid)"), {"id": jalon_id}
    )

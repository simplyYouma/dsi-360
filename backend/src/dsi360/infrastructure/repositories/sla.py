"""Accès aux règles SLA paramétrables (core.sla_regle)."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.sla import SLA_DEFAUT, CiblesSla


async def charger_matrice(session: AsyncSession) -> dict[int, CiblesSla]:
    """Renvoie la matrice {priorité: cibles} depuis la base (repli sur les valeurs par défaut)."""
    lignes = (
        await session.execute(
            text(
                "SELECT priorite, prise_en_charge_minutes, resolution_minutes "
                "FROM core.sla_regle"
            )
        )
    ).all()
    if not lignes:
        return SLA_DEFAUT
    return {
        int(r[0]): CiblesSla(prise_en_charge_minutes=int(r[1]), resolution_minutes=int(r[2]))
        for r in lignes
    }


async def lister(session: AsyncSession) -> list[dict[str, Any]]:
    lignes = (
        await session.execute(
            text(
                "SELECT priorite, prise_en_charge_minutes, resolution_minutes "
                "FROM core.sla_regle ORDER BY priorite"
            )
        )
    ).mappings().all()
    return [dict(x) for x in lignes]


async def definir(
    session: AsyncSession, priorite: int, prise_en_charge_minutes: int, resolution_minutes: int
) -> None:
    await session.execute(
        text(
            "INSERT INTO core.sla_regle (priorite, prise_en_charge_minutes, resolution_minutes) "
            "VALUES (:p, :pc, :res) "
            "ON CONFLICT (priorite) DO UPDATE SET "
            "prise_en_charge_minutes = excluded.prise_en_charge_minutes, "
            "resolution_minutes = excluded.resolution_minutes, maj_le = now()"
        ),
        {"p": priorite, "pc": prise_en_charge_minutes, "res": resolution_minutes},
    )

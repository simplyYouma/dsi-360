"""Accès aux règles SLA paramétrables (core.sla_regle), par (module, priorité)."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.sla import SLA_DEFAUT, CiblesSla


async def charger_matrice(session: AsyncSession, module: str) -> dict[int, CiblesSla]:
    """Matrice {priorité: cibles} d'un module (repli sur les valeurs par défaut si absent)."""
    lignes = (
        await session.execute(
            text(
                "SELECT priorite, prise_en_charge_minutes, resolution_minutes "
                "FROM core.sla_regle WHERE module = :m"
            ),
            {"m": module},
        )
    ).all()
    if not lignes:
        return SLA_DEFAUT
    return {
        int(r[0]): CiblesSla(prise_en_charge_minutes=int(r[1]), resolution_minutes=int(r[2]))
        for r in lignes
    }


async def lister(session: AsyncSession, module: str) -> list[dict[str, Any]]:
    """Les 5 règles d'un module ; complète avec les valeurs par défaut si certaines manquent."""
    lignes = (
        await session.execute(
            text(
                "SELECT priorite, prise_en_charge_minutes, resolution_minutes "
                "FROM core.sla_regle WHERE module = :m ORDER BY priorite"
            ),
            {"m": module},
        )
    ).mappings().all()
    existantes: dict[int, dict[str, Any]] = {int(x["priorite"]): dict(x) for x in lignes}
    resultat: list[dict[str, Any]] = []
    for p in range(1, 6):
        if p in existantes:
            resultat.append(existantes[p])
        else:
            cibles = SLA_DEFAUT[p]
            resultat.append(
                {
                    "priorite": p,
                    "prise_en_charge_minutes": cibles.prise_en_charge_minutes,
                    "resolution_minutes": cibles.resolution_minutes,
                }
            )
    return resultat


async def definir(
    session: AsyncSession,
    module: str,
    priorite: int,
    prise_en_charge_minutes: int,
    resolution_minutes: int,
) -> None:
    await session.execute(
        text(
            "INSERT INTO core.sla_regle "
            "(module, priorite, prise_en_charge_minutes, resolution_minutes) "
            "VALUES (:m, :p, :pc, :res) "
            "ON CONFLICT (module, priorite) DO UPDATE SET "
            "prise_en_charge_minutes = excluded.prise_en_charge_minutes, "
            "resolution_minutes = excluded.resolution_minutes, maj_le = now()"
        ),
        {"m": module, "p": priorite, "pc": prise_en_charge_minutes, "res": resolution_minutes},
    )

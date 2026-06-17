"""Repository des activités (table générique core.activite, filtré par module)."""

from datetime import datetime
from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.activite import PREFIXE_REFERENCE

_LISTE_CHAMPS = """
    a.id::text AS id, a.reference, a.module, a.titre, a.statut, a.priorite, a.impact, a.urgence,
    a.sla_prise_en_charge_le, a.sla_resolution_le, a.cree_le, a.resolu_le, a.cloture_le,
    c.libelle AS categorie, d.code AS direction,
    r.prenom AS resp_prenom, r.nom AS resp_nom, r.email AS resp_email
"""

_BASE = """
    FROM core.activite a
    LEFT JOIN core.categorie c ON c.id = a.categorie_id
    LEFT JOIN core.direction d ON d.id = a.direction_id
    LEFT JOIN core.utilisateur r ON r.id = a.responsable_id
    WHERE a.module = :module
"""


async def prochaine_reference(session: AsyncSession, module: str, annee: int) -> str:
    prefixe = PREFIXE_REFERENCE[module]
    # Sérialise la numérotation par module pour éviter les doublons concurrents.
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:m))"), {"m": module})
    motif = f"{prefixe}-{annee}-%"
    n = await session.scalar(
        text("SELECT count(*) FROM core.activite WHERE module = :m AND reference LIKE :p"),
        {"m": module, "p": motif},
    )
    return f"{prefixe}-{annee}-{(n or 0) + 1:05d}"


async def creer(session: AsyncSession, champs: dict[str, Any]) -> str:
    requete = text(
        "INSERT INTO core.activite "
        "(reference, module, titre, description, direction_id, categorie_id, demandeur_id, "
        " responsable_id, impact, urgence, priorite, statut, sla_prise_en_charge_le, "
        " sla_resolution_le) "
        "VALUES (:reference, :module, :titre, :description, cast(:direction_id as uuid), "
        " cast(:categorie_id as uuid), cast(:demandeur_id as uuid), cast(:responsable_id as uuid), "
        " :impact, :urgence, :priorite, :statut, :sla_prise_en_charge_le, :sla_resolution_le) "
        "RETURNING id::text"
    )
    identifiant = await session.scalar(requete, champs)
    return str(identifiant)


async def par_id(session: AsyncSession, module: str, identifiant: str) -> RowMapping | None:
    requete = text(
        f"SELECT {_LISTE_CHAMPS}, a.description, a.donnees {_BASE} AND a.id::text = :id"
    )
    resultat = await session.execute(requete, {"module": module, "id": identifiant})
    return resultat.mappings().first()


async def lister(
    session: AsyncSession,
    module: str,
    *,
    direction: str | None,
    statut: str | None,
    page: int,
    taille: int,
) -> tuple[list[RowMapping], int]:
    params: dict[str, Any] = {"module": module}
    filtres = ""
    if direction is not None:
        filtres += " AND d.code = :direction"
        params["direction"] = direction
    if statut is not None:
        filtres += " AND a.statut = :statut"
        params["statut"] = statut

    total = await session.scalar(text(f"SELECT count(*) {_BASE}{filtres}"), params) or 0
    params_page = {**params, "limite": taille, "decalage": (page - 1) * taille}
    lignes = await session.execute(
        text(
            f"SELECT {_LISTE_CHAMPS} {_BASE}{filtres} "
            "ORDER BY a.cree_le DESC LIMIT :limite OFFSET :decalage"
        ),
        params_page,
    )
    return list(lignes.mappings().all()), total


async def changer_statut(
    session: AsyncSession,
    identifiant: str,
    statut: str,
    horodatages: dict[str, datetime],
) -> None:
    fixes = "".join(f", {colonne} = :{colonne}" for colonne in horodatages)
    params: dict[str, Any] = {"id": identifiant, "statut": statut, **horodatages}
    await session.execute(
        text(f"UPDATE core.activite SET statut = :statut{fixes} WHERE id::text = :id"),
        params,
    )

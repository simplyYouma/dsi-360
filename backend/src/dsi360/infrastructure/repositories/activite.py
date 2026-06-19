"""Repository des activités (table générique core.activite, filtré par module)."""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.activite import PREFIXE_REFERENCE
from dsi360.domain.etats import STATUTS_TERMINAUX

_LISTE_CHAMPS = """
    a.id::text AS id, a.reference, a.module, a.titre, a.statut, a.priorite, a.impact, a.urgence,
    a.sla_prise_en_charge_le, a.sla_resolution_le, a.cree_le, a.resolu_le, a.cloture_le, a.donnees,
    c.libelle AS categorie, d.code AS direction,
    r.id::text AS resp_id, r.prenom AS resp_prenom, r.nom AS resp_nom, r.email AS resp_email,
    dem.nom_complet AS demandeur_nom,
    (SELECT count(*) FROM core.commentaire cm WHERE cm.activite_id = a.id) AS nb_commentaires
"""

_BASE = """
    FROM core.activite a
    LEFT JOIN core.categorie c ON c.id = a.categorie_id
    LEFT JOIN core.direction d ON d.id = a.direction_id
    LEFT JOIN core.utilisateur r ON r.id = a.responsable_id
    LEFT JOIN core.demandeur dem ON dem.id = a.demandeur_externe_id
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
    champs.setdefault("impact", None)
    champs.setdefault("urgence", None)
    champs.setdefault("priorite", None)
    champs.setdefault("categorie_id", None)
    champs.setdefault("sla_prise_en_charge_le", None)
    champs.setdefault("sla_resolution_le", None)
    champs.setdefault("donnees", None)
    champs.setdefault("demandeur_externe_id", None)
    requete = text(
        "INSERT INTO core.activite "
        "(reference, module, titre, description, direction_id, categorie_id, demandeur_id, "
        " demandeur_externe_id, responsable_id, impact, urgence, priorite, statut, "
        " sla_prise_en_charge_le, sla_resolution_le, donnees) "
        "VALUES (:reference, :module, :titre, :description, cast(:direction_id as uuid), "
        " cast(:categorie_id as uuid), cast(:demandeur_id as uuid), "
        " cast(:demandeur_externe_id as uuid), cast(:responsable_id as uuid), "
        " :impact, :urgence, :priorite, :statut, :sla_prise_en_charge_le, :sla_resolution_le, "
        " coalesce(cast(:donnees as jsonb), '{}'::jsonb)) "
        "RETURNING id::text"
    )
    identifiant = await session.scalar(requete, champs)
    return str(identifiant)


async def par_id(session: AsyncSession, module: str, identifiant: str) -> RowMapping | None:
    requete = text(f"SELECT {_LISTE_CHAMPS}, a.description {_BASE} AND a.id::text = :id")
    resultat = await session.execute(requete, {"module": module, "id": identifiant})
    return resultat.mappings().first()


async def maj_donnees(session: AsyncSession, identifiant: str, fragment: dict[str, Any]) -> None:
    """Fusionne un fragment JSON dans la colonne donnees (ex. avancement d'un projet)."""
    await session.execute(
        text(
            "UPDATE core.activite SET donnees = donnees || cast(:f as jsonb) WHERE id::text = :id"
        ),
        {"id": identifiant, "f": json.dumps(fragment)},
    )
    await session.commit()


def _clause_etat(etat: str | None, params: dict[str, Any]) -> str:
    """Filtre 'en_cours' (hors statuts terminaux) ou 'termines' (statuts terminaux)."""
    if etat not in ("en_cours", "termines"):
        return ""
    termes = sorted(STATUTS_TERMINAUX)
    placeholders = ", ".join(f":term{i}" for i in range(len(termes)))
    for i, t in enumerate(termes):
        params[f"term{i}"] = t
    operateur = "NOT IN" if etat == "en_cours" else "IN"
    return f" AND a.statut {operateur} ({placeholders})"


async def lister(
    session: AsyncSession,
    module: str,
    *,
    direction: str | None,
    statut: str | None,
    page: int,
    taille: int,
    responsable_id: str | None = None,
    non_assigne: bool = False,
    q: str | None = None,
    etat: str | None = None,
) -> tuple[list[RowMapping], int]:
    params: dict[str, Any] = {"module": module}
    filtres = ""
    if direction is not None:
        filtres += " AND d.code = :direction"
        params["direction"] = direction
    if statut is not None:
        filtres += " AND a.statut = :statut"
        params["statut"] = statut
    if responsable_id is not None:
        filtres += " AND a.responsable_id = cast(:resp as uuid)"
        params["resp"] = responsable_id
    if non_assigne:
        filtres += " AND a.responsable_id IS NULL"
    if q is not None and q.strip() != "":
        filtres += " AND (a.reference ILIKE :q OR a.titre ILIKE :q)"
        params["q"] = f"%{q.strip()}%"
    filtres += _clause_etat(etat, params)

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


async def lister_tout(
    session: AsyncSession, module: str, *, direction: str | None, limite: int = 5000
) -> list[RowMapping]:
    """Toutes les activités du périmètre (sans pagination) — pour les exports."""
    params: dict[str, Any] = {"module": module, "limite": limite}
    cond = ""
    if direction is not None:
        cond = " AND d.code = :direction"
        params["direction"] = direction
    lignes = await session.execute(
        text(f"SELECT {_LISTE_CHAMPS} {_BASE}{cond} ORDER BY a.cree_le DESC LIMIT :limite"),
        params,
    )
    return list(lignes.mappings().all())


async def assigner(session: AsyncSession, identifiant: str, responsable_id: str | None) -> None:
    """Affecte (ou retire) le gestionnaire DSI d'une activité."""
    await session.execute(
        text(
            "UPDATE core.activite SET responsable_id = cast(:resp as uuid) WHERE id::text = :id"
        ),
        {"id": identifiant, "resp": responsable_id},
    )


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

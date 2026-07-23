"""Modèles de jalons rattachés à un type de projet (core.modele_jalon).

Un modèle décrit le déroulé habituel d'un type de projet. À la création d'un projet, il est
**recopié** en jalons réels : les jalons appartiennent ensuite au projet et se modifient
librement. Retoucher un modèle ne rejoue donc jamais l'histoire des projets déjà ouverts.
"""

from typing import Any, cast

from sqlalchemy import CursorResult, RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

_CHAMPS = "id::text AS id, categorie_id::text AS categorie_id, titre, ordre"


async def lister(session: AsyncSession, categorie_id: str) -> list[RowMapping]:
    lignes = await session.execute(
        text(
            f"SELECT {_CHAMPS} FROM core.modele_jalon "
            "WHERE categorie_id = cast(:c as uuid) ORDER BY ordre, titre"
        ),
        {"c": categorie_id},
    )
    return list(lignes.mappings().all())


async def creer(session: AsyncSession, categorie_id: str, titre: str) -> RowMapping | None:
    """Ajoute un jalon au modèle. `None` si le titre y figure déjà — geste sans effet, pas faute."""
    ordre = await session.scalar(
        text(
            "SELECT coalesce(max(ordre), 0) + 1 FROM core.modele_jalon "
            "WHERE categorie_id = cast(:c as uuid)"
        ),
        {"c": categorie_id},
    )
    ligne = (
        await session.execute(
            text(
                "INSERT INTO core.modele_jalon (categorie_id, titre, ordre) "
                "VALUES (cast(:c as uuid), :t, :o) "
                "ON CONFLICT (categorie_id, titre) DO NOTHING "
                f"RETURNING {_CHAMPS}"
            ),
            {"c": categorie_id, "t": titre, "o": ordre},
        )
    ).mappings().first()
    return ligne


async def supprimer(session: AsyncSession, modele_id: str, categorie_id: str) -> bool:
    resultat = await session.execute(
        text(
            "DELETE FROM core.modele_jalon "
            "WHERE id = cast(:id as uuid) AND categorie_id = cast(:c as uuid)"
        ),
        {"id": modele_id, "c": categorie_id},
    )
    return int(cast(CursorResult[object], resultat).rowcount or 0) > 0


async def compter_par_categorie(session: AsyncSession, module: str) -> dict[str, int]:
    """Nombre de jalons modèles par type, pour afficher « 6 jalons » en face de chaque type."""
    lignes = await session.execute(
        text(
            "SELECT c.id::text AS id, count(m.id) AS n "
            "FROM core.categorie c LEFT JOIN core.modele_jalon m ON m.categorie_id = c.id "
            "WHERE c.module = :module GROUP BY c.id"
        ),
        {"module": module},
    )
    return {ligne["id"]: int(ligne["n"]) for ligne in lignes.mappings().all()}


async def poser_sur_projet(
    session: AsyncSession, activite_id: str, categorie_id: str
) -> int:
    """Recopie les jalons du modèle sur un projet **qui n'en a aucun**. Renvoie le nombre posé.

    La garde « aucun jalon » est la sécurité : changer le type d'un projet déjà jalonné ne doit
    ni doubler ses jalons ni effacer ceux que le chef de projet a écrits lui-même.
    """
    resultat = await session.execute(
        text(
            "INSERT INTO core.jalon (activite_id, titre, ordre) "
            "SELECT cast(:a as uuid), m.titre, m.ordre FROM core.modele_jalon m "
            "WHERE m.categorie_id = cast(:c as uuid) "
            "  AND NOT EXISTS (SELECT 1 FROM core.jalon j WHERE j.activite_id = cast(:a as uuid))"
        ),
        {"a": activite_id, "c": categorie_id},
    )
    return int(cast(CursorResult[object], resultat).rowcount or 0)


async def categorie(session: AsyncSession, categorie_id: str, module: str) -> dict[str, Any] | None:
    ligne = (
        await session.execute(
            text(
                "SELECT id::text AS id, code, libelle FROM core.categorie "
                "WHERE id = cast(:id as uuid) AND module = :module"
            ),
            {"id": categorie_id, "module": module},
        )
    ).mappings().first()
    return dict(ligne) if ligne is not None else None

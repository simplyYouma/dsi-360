"""Repositories de l'EOD : le déroulé de référence (core.eod_modele_etape) et les étapes
réellement pointées d'une soirée (core.eod_etape).

Même partage qu'entre un modèle de jalons et les jalons d'un projet : le modèle décrit ce qui se
fait tous les soirs, les étapes appartiennent à la soirée dès qu'elles sont posées. Corriger le
modèle ne réécrit donc jamais une nuit passée — c'est la propriété qui rend le rapport opposable.
"""

from typing import Any, cast

from sqlalchemy import CursorResult, RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

_CHAMPS = (
    "id::text AS id, section, libelle, nature, aide, ordre, statut, debut, fin, valeur, notes"
)
_CHAMPS_MODELE = "id::text AS id, section, libelle, nature, aide, ordre, actif"

#: Champs qu'une mise à jour d'étape peut toucher. Tout le reste (section, libellé, nature) décrit
#: le déroulé et ne se retouche qu'en ajoutant ou en retirant une étape.
_MODIFIABLES = frozenset({"statut", "debut", "fin", "valeur", "notes", "ordre"})


# --- Déroulé de référence ------------------------------------------------------------------------


async def lister_modele(session: AsyncSession, *, actifs_seuls: bool = True) -> list[RowMapping]:
    clause = "WHERE actif" if actifs_seuls else ""
    lignes = await session.execute(
        text(f"SELECT {_CHAMPS_MODELE} FROM core.eod_modele_etape {clause} ORDER BY ordre, libelle")
    )
    return list(lignes.mappings().all())


async def poser_le_deroule(session: AsyncSession, activite_id: str) -> int:
    """Recopie le déroulé de référence sur une soirée **qui n'a aucune étape**. Renvoie le nombre.

    La garde « aucune étape » est la sécurité : relancer la pose sur une soirée déjà pointée
    doublerait les lignes et effacerait le travail de l'opérateur au milieu de sa nuit.
    """
    resultat = await session.execute(
        text(
            "INSERT INTO core.eod_etape (activite_id, section, libelle, nature, aide, ordre) "
            "SELECT cast(:a as uuid), m.section, m.libelle, m.nature, m.aide, m.ordre "
            "FROM core.eod_modele_etape m WHERE m.actif "
            "  AND NOT EXISTS (SELECT 1 FROM core.eod_etape e "
            "                  WHERE e.activite_id = cast(:a as uuid))"
        ),
        {"a": activite_id},
    )
    return int(cast(CursorResult[object], resultat).rowcount or 0)


# --- Étapes d'une soirée -------------------------------------------------------------------------


async def lister(session: AsyncSession, activite_id: str) -> list[RowMapping]:
    lignes = await session.execute(
        text(
            f"SELECT {_CHAMPS} FROM core.eod_etape WHERE activite_id = cast(:a as uuid) "
            "ORDER BY ordre, cree_le"
        ),
        {"a": activite_id},
    )
    return list(lignes.mappings().all())


async def par_id(session: AsyncSession, etape_id: str, activite_id: str) -> RowMapping | None:
    resultat = await session.execute(
        text(
            f"SELECT {_CHAMPS} FROM core.eod_etape "
            "WHERE id = cast(:id as uuid) AND activite_id = cast(:a as uuid)"
        ),
        {"id": etape_id, "a": activite_id},
    )
    return resultat.mappings().first()


async def statuts(session: AsyncSession, activite_id: str) -> list[str]:
    """Les seuls statuts, pour calculer l'avancement sans rapatrier tout le déroulé."""
    lignes = await session.execute(
        text("SELECT statut FROM core.eod_etape WHERE activite_id = cast(:a as uuid)"),
        {"a": activite_id},
    )
    return [str(ligne[0]) for ligne in lignes.all()]


async def creer(session: AsyncSession, activite_id: str, champs: dict[str, Any]) -> RowMapping:
    """Ajoute une étape à une soirée. Sans rang donné, elle se range en fin de section."""
    ordre = champs.get("ordre")
    if ordre is None:
        ordre = await session.scalar(
            text(
                "SELECT coalesce(max(ordre), 0) + 1 FROM core.eod_etape "
                "WHERE activite_id = cast(:a as uuid)"
            ),
            {"a": activite_id},
        )
    ligne = (
        await session.execute(
            text(
                "INSERT INTO core.eod_etape "
                "(activite_id, section, libelle, nature, aide, ordre, notes) "
                "VALUES (cast(:a as uuid), :section, :libelle, :nature, :aide, :ordre, :notes) "
                f"RETURNING {_CHAMPS}"
            ),
            {
                "a": activite_id,
                "section": champs["section"],
                "libelle": champs["libelle"],
                "nature": champs.get("nature", "horaire"),
                "aide": champs.get("aide"),
                "ordre": ordre,
                "notes": champs.get("notes"),
            },
        )
    ).mappings().one()
    return ligne


async def maj(session: AsyncSession, etape_id: str, champs: dict[str, Any]) -> None:
    fixes = {c: v for c, v in champs.items() if c in _MODIFIABLES}
    if not fixes:
        return
    fragments = ", ".join(f"{c} = :{c}" for c in fixes)
    await session.execute(
        text(f"UPDATE core.eod_etape SET {fragments}, maj_le = now() WHERE id = cast(:id as uuid)"),
        {"id": etape_id, **fixes},
    )


async def supprimer(session: AsyncSession, etape_id: str) -> None:
    await session.execute(
        text("DELETE FROM core.eod_etape WHERE id = cast(:id as uuid)"), {"id": etape_id}
    )


async def agregats(session: AsyncSession, activite_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Ce que les étapes disent de chaque soirée, en **une** requête pour toute la page.

    Aller compter les étapes soirée par soirée ferait quinze requêtes pour afficher quinze lignes ;
    la liste s'alourdirait à mesure que la DSI garde ses nuits — exactement l'inverse du but.
    """
    if not activite_ids:
        return {}
    lignes = await session.execute(
        text(
            "SELECT activite_id::text AS id, count(*) AS total, "
            "  count(*) FILTER (WHERE statut IN ('Complété', 'Anomalie', 'Non applicable')) "
            "    AS regles, "
            "  count(*) FILTER (WHERE statut = 'Anomalie') AS anomalies, "
            "  min(debut) AS debut, max(fin) AS fin "
            "FROM core.eod_etape WHERE activite_id::text = ANY(:ids) "
            "GROUP BY activite_id"
        ),
        {"ids": activite_ids},
    )
    return {
        str(ligne["id"]): {
            "nb_etapes": int(ligne["total"]),
            "reste": int(ligne["total"]) - int(ligne["regles"]),
            "anomalies": int(ligne["anomalies"]),
            "debut_effectif": ligne["debut"],
            "fin_effective": ligne["fin"],
        }
        for ligne in lignes.mappings().all()
    }


async def journee_existante(session: AsyncSession, journee: str) -> str | None:
    """Référence de la soirée déjà ouverte pour cette date, le cas échéant.

    Permet de refuser un doublon en le **nommant** — « EOD-2026-00042 couvre déjà cette nuit » —
    plutôt que de laisser remonter une violation d'index que personne ne sait interpréter.
    """
    reference = await session.scalar(
        text(
            "SELECT reference FROM core.activite "
            "WHERE module = 'eod' AND donnees ->> 'journee' = :j"
        ),
        {"j": journee},
    )
    return None if reference is None else str(reference)

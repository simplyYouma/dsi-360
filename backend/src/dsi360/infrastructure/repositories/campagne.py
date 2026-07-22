"""Repository des campagnes d'inventaire : recensements datés du parc matériel.

L'état d'un équipement (bon, rebut, casse) n'est jamais un attribut du matériel : c'est un
constat, daté et signé, rattaché à une campagne. C'est ce qui permet de comparer une année à
l'autre — et de relever les non retrouvés, le résultat le plus précieux de l'exercice.
"""

from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

#: Constats admis à la saisie. NON_RETROUVE ne se saisit pas : il se déduit à la clôture —
#: dire « non retrouvé » en cours de campagne, c'est juste ne pas l'avoir encore recensé.
ETATS_SAISIE = ("BON", "REBUT", "CASSE")

# Chaque campagne revient avec son avancement : constats posés sur le parc actif du moment.
_LISTE = text(
    "SELECT c.id::text AS id, c.libelle, c.statut, c.ouverte_le, c.cloturee_le, "
    "u.prenom || ' ' || u.nom AS ouverte_par, "
    "count(k.equipement_id) AS constates, "
    "count(*) FILTER (WHERE k.etat = 'BON') AS bons, "
    "count(*) FILTER (WHERE k.etat = 'REBUT') AS rebuts, "
    "count(*) FILTER (WHERE k.etat = 'CASSE') AS casses, "
    "count(*) FILTER (WHERE k.etat = 'NON_RETROUVE') AS non_retrouves "
    "FROM core.campagne_inventaire c "
    "LEFT JOIN core.utilisateur u ON u.id = c.ouverte_par "
    "LEFT JOIN core.constat_inventaire k ON k.campagne_id = c.id "
    "GROUP BY c.id, u.prenom, u.nom "
    "ORDER BY c.ouverte_le DESC"
)


async def lister(session: AsyncSession) -> list[RowMapping]:
    return list((await session.execute(_LISTE)).mappings().all())


async def par_id(session: AsyncSession, ident: str) -> RowMapping | None:
    lignes = await lister(session)
    return next((c for c in lignes if c["id"] == ident), None)


async def ouverte(session: AsyncSession) -> RowMapping | None:
    """La campagne en cours, s'il y en a une — l'index unique garantit qu'il n'y en a qu'une."""
    r = await session.execute(
        text(
            "SELECT id::text AS id, libelle FROM core.campagne_inventaire "
            "WHERE statut = 'OUVERTE'"
        )
    )
    return r.mappings().first()


async def creer(session: AsyncSession, libelle: str, acteur_id: str) -> str:
    ident = await session.scalar(
        text(
            "INSERT INTO core.campagne_inventaire (libelle, ouverte_par) "
            "VALUES (btrim(:l), cast(:a as uuid)) RETURNING id::text"
        ),
        {"l": libelle, "a": acteur_id},
    )
    return str(ident)


async def poser_constat(
    session: AsyncSession, campagne_id: str, equipement_id: str, etat: str, acteur_id: str
) -> None:
    """Un constat par équipement et par campagne : reposer remplace le précédent."""
    await session.execute(
        text(
            "INSERT INTO core.constat_inventaire "
            "(campagne_id, equipement_id, etat, constate_par) "
            "VALUES (cast(:c as uuid), cast(:e as uuid), :etat, cast(:a as uuid)) "
            "ON CONFLICT (campagne_id, equipement_id) "
            "DO UPDATE SET etat = excluded.etat, constate_le = now(), "
            "constate_par = excluded.constate_par"
        ),
        {"c": campagne_id, "e": equipement_id, "etat": etat, "a": acteur_id},
    )


async def retirer_constat(session: AsyncSession, campagne_id: str, equipement_id: str) -> None:
    """Annuler un constat posé par erreur : l'équipement redevient « à recenser »."""
    await session.execute(
        text(
            "DELETE FROM core.constat_inventaire "
            "WHERE campagne_id = cast(:c as uuid) AND equipement_id = cast(:e as uuid)"
        ),
        {"c": campagne_id, "e": equipement_id},
    )


async def cloturer(session: AsyncSession, campagne_id: str, acteur_id: str) -> int:
    """Clôture la campagne et pose NON_RETROUVE sur tout matériel actif jamais recensé.

    Retourne le nombre de non retrouvés — c'est le chiffre que la clôture vient chercher.
    """
    non_retrouves = await session.scalar(
        text(
            "WITH poses AS ("
            "  INSERT INTO core.constat_inventaire "
            "  (campagne_id, equipement_id, etat, constate_par) "
            "  SELECT cast(:c as uuid), e.id, 'NON_RETROUVE', cast(:a as uuid) "
            "  FROM core.equipement e "
            "  WHERE e.actif AND NOT EXISTS ("
            "    SELECT 1 FROM core.constat_inventaire k "
            "    WHERE k.campagne_id = cast(:c as uuid) AND k.equipement_id = e.id) "
            "  RETURNING 1) "
            "SELECT count(*) FROM poses"
        ),
        {"c": campagne_id, "a": acteur_id},
    )
    await session.execute(
        text(
            "UPDATE core.campagne_inventaire SET statut = 'CLOTUREE', cloturee_le = now() "
            "WHERE id = cast(:c as uuid)"
        ),
        {"c": campagne_id},
    )
    return int(non_retrouves or 0)


# Le recensement, équipement par équipement : le parc actif, chacun avec son constat (ou non).
_RECENSEMENT = text(
    "SELECT e.id::text AS id, e.code_immo, e.designation, e.numero_serie, "
    "emp.libelle AS emplacement, "
    "coalesce(u.prenom || ' ' || u.nom, e.matricule_brut) AS detenteur, "
    "k.etat, k.constate_le, ku.prenom || ' ' || ku.nom AS constate_par "
    "FROM core.equipement e "
    "LEFT JOIN core.emplacement emp ON emp.id = e.emplacement_id "
    "LEFT JOIN core.utilisateur u ON u.id = e.detenteur_id "
    "LEFT JOIN core.constat_inventaire k "
    "  ON k.campagne_id = cast(:c as uuid) AND k.equipement_id = e.id "
    "LEFT JOIN core.utilisateur ku ON ku.id = k.constate_par "
    "WHERE e.actif OR k.etat IS NOT NULL "
    "ORDER BY (k.etat IS NOT NULL), e.designation, e.code_immo"
)


async def recensement(session: AsyncSession, campagne_id: str) -> list[dict[str, Any]]:
    lignes = await session.execute(_RECENSEMENT, {"c": campagne_id})
    return [dict(r) for r in lignes.mappings().all()]


async def parc_actif(session: AsyncSession) -> int:
    return int(
        await session.scalar(text("SELECT count(*) FROM core.equipement WHERE actif")) or 0
    )

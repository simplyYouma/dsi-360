"""Repository de l'inventaire : équipements et leurs deux référentiels de localisation."""

from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

_CHAMPS = """
    e.id::text AS id, e.code_immo, e.numero_serie, e.modele, e.designation,
    e.emplacement_id::text AS emplacement_id, emp.libelle AS emplacement,
    e.departement_id::text AS departement_id, dep.libelle AS departement,
    e.detenteur_id::text AS detenteur_id, e.matricule_brut, e.detenteur_externe,
    u.prenom AS det_prenom, u.nom AS det_nom, u.matricule AS det_matricule,
    e.taux, e.date_acquisition, e.duree_annees, e.valeur_acquisition,
    e.source, e.actif, e.cree_le, e.maj_le
"""

_BASE = """
    FROM core.equipement e
    LEFT JOIN core.emplacement emp ON emp.id = e.emplacement_id
    LEFT JOIN core.departement_equipement dep ON dep.id = e.departement_id
    LEFT JOIN core.utilisateur u ON u.id = e.detenteur_id
    WHERE 1 = 1
"""

# Champs modifiables à l'écran. Liste blanche : jamais de nom de colonne venu de l'appelant.
CHAMPS_MODIFIABLES = frozenset(
    {
        "code_immo",
        "numero_serie",
        "modele",
        "designation",
        "emplacement_id",
        "departement_id",
        "detenteur_id",
        "detenteur_externe",
        "matricule_brut",
        "taux",
        "date_acquisition",
        "duree_annees",
        "valeur_acquisition",
        "actif",
    }
)
_UUID = frozenset({"emplacement_id", "departement_id", "detenteur_id"})


async def par_id(session: AsyncSession, identifiant: str) -> RowMapping | None:
    resultat = await session.execute(
        text(f"SELECT {_CHAMPS} {_BASE} AND e.id::text = :id"), {"id": identifiant}
    )
    return resultat.mappings().first()


async def par_code_immo(session: AsyncSession, code: str) -> RowMapping | None:
    """Recherche par code d'immobilisation — la clé de rapprochement de l'import."""
    resultat = await session.execute(
        text(f"SELECT {_CHAMPS} {_BASE} AND upper(btrim(e.code_immo)) = upper(btrim(:c))"),
        {"c": code},
    )
    return resultat.mappings().first()


def _filtres(
    q: str | None,
    emplacement_id: str | None,
    departement_id: str | None,
    detenteur_id: str | None,
    actif: bool | None,
    params: dict[str, Any],
) -> str:
    """Conditions de liste. La recherche passe outre les autres filtres — comme pour les
    activités : chercher, c'est vouloir retrouver un matériel, pas fouiller la vue courante."""
    recherche = q is not None and q.strip() != ""
    conditions = ""
    if recherche and q is not None:
        # Le matériel se cherche par ce qui est écrit dessus : code immo, n° de série, modèle,
        # désignation — mais aussi par son détenteur, qu'on connaît souvent mieux que le code.
        conditions += (
            " AND (e.code_immo ILIKE :q OR e.numero_serie ILIKE :q OR e.modele ILIKE :q"
            " OR e.designation ILIKE :q OR e.matricule_brut ILIKE :q"
            " OR e.detenteur_externe ILIKE :q"
            " OR (u.prenom || ' ' || u.nom) ILIKE :q OR u.matricule ILIKE :q"
            " OR emp.libelle ILIKE :q OR dep.libelle ILIKE :q)"
        )
        params["q"] = f"%{q.strip()}%"
        return conditions
    if emplacement_id is not None:
        conditions += " AND e.emplacement_id = cast(:emp as uuid)"
        params["emp"] = emplacement_id
    if departement_id is not None:
        conditions += " AND e.departement_id = cast(:dep as uuid)"
        params["dep"] = departement_id
    if detenteur_id is not None:
        conditions += " AND e.detenteur_id = cast(:det as uuid)"
        params["det"] = detenteur_id
    if actif is not None:
        conditions += " AND e.actif = :actif"
        params["actif"] = actif
    return conditions


async def lister(
    session: AsyncSession,
    *,
    page: int,
    taille: int,
    q: str | None = None,
    emplacement_id: str | None = None,
    departement_id: str | None = None,
    detenteur_id: str | None = None,
    actif: bool | None = True,
) -> tuple[list[RowMapping], int]:
    params: dict[str, Any] = {}
    conditions = _filtres(q, emplacement_id, departement_id, detenteur_id, actif, params)
    total = await session.scalar(text(f"SELECT count(*) {_BASE}{conditions}"), params) or 0
    lignes = await session.execute(
        text(
            f"SELECT {_CHAMPS} {_BASE}{conditions} "
            "ORDER BY e.designation, e.code_immo LIMIT :limite OFFSET :decalage"
        ),
        {**params, "limite": taille, "decalage": (page - 1) * taille},
    )
    return list(lignes.mappings().all()), int(total)


async def lister_tout(session: AsyncSession, limite: int = 20000) -> list[RowMapping]:
    """Parc complet, sans pagination — pour les exports."""
    lignes = await session.execute(
        text(f"SELECT {_CHAMPS} {_BASE} ORDER BY e.designation, e.code_immo LIMIT :l"),
        {"l": limite},
    )
    return list(lignes.mappings().all())


async def compter(session: AsyncSession) -> dict[str, int | float]:
    """Compteurs de l'en-tête de liste : effectif, sorties du parc, valeur d'acquisition."""
    ligne = (
        await session.execute(
            text(
                "SELECT count(*) AS total, "
                "count(*) FILTER (WHERE e.actif) AS en_service, "
                "count(*) FILTER (WHERE NOT e.actif) AS sortis, "
                "count(*) FILTER (WHERE e.detenteur_id IS NULL) AS sans_detenteur, "
                "coalesce(sum(e.valeur_acquisition) FILTER (WHERE e.actif), 0) AS valeur "
                "FROM core.equipement e"
            )
        )
    ).mappings().one()
    return {
        "total": int(ligne["total"]),
        "en_service": int(ligne["en_service"]),
        "sortis": int(ligne["sortis"]),
        "sans_detenteur": int(ligne["sans_detenteur"]),
        "valeur_acquisition": float(ligne["valeur"] or 0),
    }


async def creer(session: AsyncSession, champs: dict[str, Any]) -> str:
    colonnes = [c for c in champs if c in CHAMPS_MODIFIABLES] + ["source"]
    valeurs = ", ".join(
        f"cast(:{c} as uuid)" if c in _UUID else f":{c}" for c in colonnes
    )
    identifiant = await session.scalar(
        text(
            f"INSERT INTO core.equipement ({', '.join(colonnes)}) "
            f"VALUES ({valeurs}) RETURNING id::text"
        ),
        {c: champs.get(c) for c in colonnes},
    )
    return str(identifiant)


async def maj(session: AsyncSession, identifiant: str, champs: dict[str, Any]) -> None:
    colonnes = [c for c in champs if c in CHAMPS_MODIFIABLES]
    if not colonnes:
        return
    affectations = ", ".join(
        f"{c} = cast(:{c} as uuid)" if c in _UUID else f"{c} = :{c}" for c in colonnes
    )
    await session.execute(
        text(
            f"UPDATE core.equipement SET {affectations}, maj_le = now() "
            "WHERE id = cast(:id as uuid)"
        ),
        {**{c: champs[c] for c in colonnes}, "id": identifiant},
    )


async def supprimer(session: AsyncSession, identifiant: str) -> None:
    await session.execute(
        text("DELETE FROM core.equipement WHERE id = cast(:id as uuid)"), {"id": identifiant}
    )


# --- Référentiels de localisation -----------------------------------------------------------

#: Table par clé de référentiel. Liste blanche : le nom de table ne vient jamais de l'appelant.
TABLES_REFERENTIEL = {
    "emplacements": "core.emplacement",
    "departements": "core.departement_equipement",
}


async def lister_referentiel(session: AsyncSession, cle: str) -> list[RowMapping]:
    table = TABLES_REFERENTIEL[cle]
    lignes = await session.execute(
        text(f"SELECT id::text AS id, libelle, actif FROM {table} ORDER BY libelle")
    )
    return list(lignes.mappings().all())


async def trouver_ou_creer_referentiel(
    session: AsyncSession, cle: str, libelle: str | None
) -> str | None:
    """Identifiant du libellé, créé au besoin. ``None`` si le libellé est vide.

    L'import alimente ainsi les référentiels au fil de l'eau, sans saisie préalable — comme
    `core.demandeur` pour les tickets.
    """
    if libelle is None or libelle.strip() == "":
        return None
    table = TABLES_REFERENTIEL[cle]
    identifiant = await session.scalar(
        text(
            f"INSERT INTO {table} (libelle) VALUES (btrim(:l)) "
            "ON CONFLICT (upper(btrim(libelle))) DO UPDATE SET libelle = excluded.libelle "
            "RETURNING id::text"
        ),
        {"l": libelle},
    )
    return str(identifiant)

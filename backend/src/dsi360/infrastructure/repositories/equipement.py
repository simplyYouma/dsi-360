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
    e.etat_constate, e.constate_le, e.constat_motif,
    ctrl.prenom || ' ' || ctrl.nom AS constate_par,
    e.source, e.actif, e.cree_le, e.maj_le
"""

_BASE = """
    FROM core.equipement e
    LEFT JOIN core.emplacement emp ON emp.id = e.emplacement_id
    LEFT JOIN core.departement_equipement dep ON dep.id = e.departement_id
    LEFT JOIN core.utilisateur u ON u.id = e.detenteur_id
    LEFT JOIN core.utilisateur ctrl ON ctrl.id = e.constate_par
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
        # Constat de terrain : posé par sa route dédiée, qui date et signe le contrôle.
        "etat_constate",
        "constate_le",
        "constate_par",
        "constat_motif",
    }
)
_UUID = frozenset({"emplacement_id", "departement_id", "detenteur_id", "constate_par"})

#: Au-delà de ce délai, un matériel est réputé « non contrôlé » : c'est ce que l'inventaire
#: physique vient rattraper. Ce n'est pas un verdict sur le matériel, c'est un trou de suivi.
MOIS_AVANT_CONTROLE = 12

#: Valeur de filtre pour « personne ne le détient ». Un mot-clé plutôt qu'un identifiant :
#: l'absence de détenteur n'est pas un détenteur particulier.
SANS_DETENTEUR = "AUCUN"


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


#: Vues de contrôle. « À contrôler » n'est pas un état du matériel : c'est l'absence de
#: contrôle récent — le travail de terrain qui attend.
_CLAUSE_A_CONTROLER = (
    " AND (e.constate_le IS NULL"
    f" OR e.constate_le < now() - interval '{MOIS_AVANT_CONTROLE} months')"
)


def _filtres(
    q: str | None,
    emplacement_id: str | None,
    departement_id: str | None,
    detenteur_id: str | None,
    actif: bool | None,
    params: dict[str, Any],
    etat_constate: str | None = None,
    a_controler: bool = False,
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
    if detenteur_id == SANS_DETENTEUR:
        # « Non attribué » : ni compte, ni nom libre — les rattachements qui restent à faire.
        conditions += " AND e.detenteur_id IS NULL AND e.detenteur_externe IS NULL"
    elif detenteur_id is not None:
        conditions += " AND e.detenteur_id = cast(:det as uuid)"
        params["det"] = detenteur_id
    if actif is not None:
        conditions += " AND e.actif = :actif"
        params["actif"] = actif
    if etat_constate is not None:
        conditions += " AND e.etat_constate = :etat"
        params["etat"] = etat_constate
    if a_controler:
        conditions += _CLAUSE_A_CONTROLER
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
    etat_constate: str | None = None,
    a_controler: bool = False,
) -> tuple[list[RowMapping], int]:
    params: dict[str, Any] = {}
    conditions = _filtres(
        q, emplacement_id, departement_id, detenteur_id, actif, params, etat_constate, a_controler
    )
    total = await session.scalar(text(f"SELECT count(*) {_BASE}{conditions}"), params) or 0
    # Vue « à contrôler » : le plus ancien contrôle d'abord (jamais contrôlé en tête), c'est
    # l'ordre dans lequel on va sur le terrain.
    ordre = (
        "e.constate_le ASC NULLS FIRST, e.designation"
        if a_controler
        else "e.designation, e.code_immo"
    )
    lignes = await session.execute(
        text(
            f"SELECT {_CHAMPS} {_BASE}{conditions} "
            f"ORDER BY {ordre} LIMIT :limite OFFSET :decalage"
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
    """Compteurs de l'en-tête : effectif, sorties, valeur, et l'état constaté du parc actif.

    Les constats ne comptent que sur le parc en service : l'état d'un matériel cédé l'an dernier
    ne dit plus rien de ce qu'il y a à contrôler aujourd'hui.
    """
    ligne = (
        await session.execute(
            text(
                "SELECT count(*) AS total, "
                "count(*) FILTER (WHERE e.actif) AS en_service, "
                "count(*) FILTER (WHERE NOT e.actif) AS sortis, "
                "count(*) FILTER (WHERE e.detenteur_id IS NULL) AS sans_detenteur, "
                "coalesce(sum(e.valeur_acquisition) FILTER (WHERE e.actif), 0) AS valeur, "
                "count(*) FILTER (WHERE e.actif AND e.etat_constate = 'BON') AS bons, "
                "count(*) FILTER (WHERE e.actif AND e.etat_constate = 'REBUT') AS rebuts, "
                "count(*) FILTER (WHERE e.actif AND e.etat_constate = 'CASSE') AS casses, "
                "count(*) FILTER (WHERE e.actif AND (e.constate_le IS NULL "
                f"  OR e.constate_le < now() - interval '{MOIS_AVANT_CONTROLE} months'))"
                " AS a_controler "
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
        "bons": int(ligne["bons"]),
        "rebuts": int(ligne["rebuts"]),
        "casses": int(ligne["casses"]),
        "a_controler": int(ligne["a_controler"]),
    }


async def poser_constat(
    session: AsyncSession, identifiant: str, etat: str, motif: str, acteur_id: str
) -> None:
    """Consigne ce qui a été vu sur le terrain : l'état, la date, l'auteur et le motif.

    La date et l'auteur ne viennent jamais de l'appelant : un constat vaut par le fait qu'on
    sache qui l'a posé, et quand.
    """
    await session.execute(
        text(
            "UPDATE core.equipement SET etat_constate = :etat, constat_motif = btrim(:motif), "
            "constate_le = now(), constate_par = cast(:acteur as uuid), maj_le = now() "
            "WHERE id = cast(:id as uuid)"
        ),
        {"id": identifiant, "etat": etat, "motif": motif, "acteur": acteur_id},
    )


async def retirer_constat(session: AsyncSession, identifiant: str) -> None:
    """Efface un constat posé par erreur : le matériel redevient « à contrôler »."""
    await session.execute(
        text(
            "UPDATE core.equipement SET etat_constate = NULL, constat_motif = NULL, "
            "constate_le = NULL, constate_par = NULL, maj_le = now() "
            "WHERE id = cast(:id as uuid)"
        ),
        {"id": identifiant},
    )


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

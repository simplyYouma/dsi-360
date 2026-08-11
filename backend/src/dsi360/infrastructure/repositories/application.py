"""Repository de l'inventaire applicatif : les applications et leur référentiel d'éditeurs."""

from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

_CHAMPS = """
    a.id::text AS id, a.reference, a.nom, a.processus_metier, a.fonctionnalites, a.version,
    a.editeur_id::text AS editeur_id, ed.libelle AS editeur,
    a.hebergement, a.pays_donnees, a.interfacage, a.statut, a.proprietaire,
    a.date_debut, a.date_fin, a.nb_comptes_actifs, a.lien,
    a.serveur_application, a.serveur_base, a.port,
    a.administrateur, a.administrateur_secours,
    a.actif, a.source, a.cree_le, a.maj_le
"""

_BASE = """
    FROM core.application a
    LEFT JOIN core.editeur_application ed ON ed.id = a.editeur_id
    WHERE 1 = 1
"""

# Champs modifiables à l'écran. Liste blanche : jamais de nom de colonne venu de l'appelant.
CHAMPS_MODIFIABLES = frozenset(
    {
        "nom",
        "processus_metier",
        "fonctionnalites",
        "version",
        "editeur_id",
        "hebergement",
        "pays_donnees",
        "interfacage",
        "statut",
        "proprietaire",
        "date_debut",
        "date_fin",
        "nb_comptes_actifs",
        "lien",
        "serveur_application",
        "serveur_base",
        "port",
        "administrateur",
        "administrateur_secours",
        "actif",
    }
)
_UUID = frozenset({"editeur_id"})

#: Valeur de filtre pour « aucun administrateur désigné ». Un mot-clé plutôt qu'un identifiant :
#: l'absence d'administrateur n'est pas un administrateur particulier.
SANS_ADMINISTRATEUR = "AUCUN"


async def par_id(session: AsyncSession, identifiant: str) -> RowMapping | None:
    resultat = await session.execute(
        text(f"SELECT {_CHAMPS} {_BASE} AND a.id::text = :id"), {"id": identifiant}
    )
    return resultat.mappings().first()


async def par_nom(session: AsyncSession, nom: str) -> RowMapping | None:
    """Recherche par nom — la clé d'unicité d'une application."""
    resultat = await session.execute(
        text(f"SELECT {_CHAMPS} {_BASE} AND upper(btrim(a.nom)) = upper(btrim(:n))"),
        {"n": nom},
    )
    return resultat.mappings().first()


def _filtres(
    q: str | None,
    editeur_id: str | None,
    hebergement: str | None,
    statut: str | None,
    interfacage: str | None,
    administrateur: str | None,
    actif: bool | None,
    params: dict[str, Any],
) -> str:
    """Conditions de liste. La recherche passe outre les autres filtres — comme pour le parc
    matériel : chercher, c'est vouloir retrouver une application, pas fouiller la vue courante."""
    conditions = ""
    if q is not None and q.strip() != "":
        # On cherche une application par ce qu'on en sait : son nom, son éditeur, le métier
        # qu'elle sert — et très souvent par la personne qui l'administre.
        conditions += (
            " AND (a.reference ILIKE :q OR a.nom ILIKE :q OR a.processus_metier ILIKE :q"
            " OR a.fonctionnalites ILIKE :q OR a.version ILIKE :q"
            " OR a.administrateur ILIKE :q OR a.administrateur_secours ILIKE :q"
            " OR a.proprietaire ILIKE :q OR a.serveur_application ILIKE :q"
            " OR a.serveur_base ILIKE :q OR ed.libelle ILIKE :q)"
        )
        params["q"] = f"%{q.strip()}%"
        return conditions
    if editeur_id is not None:
        conditions += " AND a.editeur_id = cast(:ed as uuid)"
        params["ed"] = editeur_id
    if hebergement is not None:
        conditions += " AND a.hebergement = :heb"
        params["heb"] = hebergement
    if statut is not None:
        conditions += " AND a.statut = :statut"
        params["statut"] = statut
    if interfacage is not None:
        conditions += " AND a.interfacage = :interf"
        params["interf"] = interfacage
    if administrateur == SANS_ADMINISTRATEUR:
        # Personne de désigné : ce sont les applications dont plus personne ne répond.
        conditions += " AND (a.administrateur IS NULL OR btrim(a.administrateur) = '')"
    elif administrateur is not None:
        conditions += (
            " AND (a.administrateur ILIKE :adm OR a.administrateur_secours ILIKE :adm)"
        )
        params["adm"] = f"%{administrateur.strip()}%"
    if actif is not None:
        conditions += " AND a.actif = :actif"
        params["actif"] = actif
    return conditions


async def lister(
    session: AsyncSession,
    *,
    page: int,
    taille: int,
    q: str | None = None,
    editeur_id: str | None = None,
    hebergement: str | None = None,
    statut: str | None = None,
    interfacage: str | None = None,
    administrateur: str | None = None,
    actif: bool | None = True,
) -> tuple[list[RowMapping], int]:
    params: dict[str, Any] = {}
    conditions = _filtres(
        q, editeur_id, hebergement, statut, interfacage, administrateur, actif, params
    )
    total = await session.scalar(text(f"SELECT count(*) {_BASE}{conditions}"), params) or 0
    lignes = await session.execute(
        text(f"SELECT {_CHAMPS} {_BASE}{conditions} ORDER BY a.nom LIMIT :limite OFFSET :decalage"),
        {**params, "limite": taille, "decalage": (page - 1) * taille},
    )
    return list(lignes.mappings().all()), int(total)


async def lister_tout(session: AsyncSession, limite: int = 20000) -> list[RowMapping]:
    """Parc applicatif complet, sans pagination — pour les exports et les analyses."""
    lignes = await session.execute(
        text(f"SELECT {_CHAMPS} {_BASE} ORDER BY a.nom LIMIT :l"), {"l": limite}
    )
    return list(lignes.mappings().all())


async def compter(session: AsyncSession) -> dict[str, int]:
    """Compteurs de l'en-tête : effectif, hébergement, interfaçage, et les trous de suivi.

    « Sans administrateur » n'est pas un détail de saisie : c'est une application dont plus
    personne ne répond — la première chose à corriger dans un inventaire applicatif.
    """
    ligne = (
        await session.execute(
            text(
                "SELECT count(*) AS total, "
                "count(*) FILTER (WHERE a.actif) AS actives, "
                "count(*) FILTER (WHERE NOT a.actif) AS retirees, "
                "count(*) FILTER (WHERE a.actif AND a.hebergement = 'INTERNE') AS internes, "
                "count(*) FILTER (WHERE a.actif AND a.hebergement = 'EXTERNE') AS externes, "
                "count(*) FILTER (WHERE a.actif AND a.interfacage = 'OUI') AS interfacees, "
                "count(*) FILTER (WHERE a.actif AND (a.administrateur IS NULL "
                "  OR btrim(a.administrateur) = '')) AS sans_administrateur, "
                "count(*) FILTER (WHERE a.actif AND (a.administrateur_secours IS NULL "
                "  OR btrim(a.administrateur_secours) = '')) AS sans_secours "
                "FROM core.application a"
            )
        )
    ).mappings().one()
    return {str(cle): int(valeur) for cle, valeur in ligne.items()}


async def creer(session: AsyncSession, champs: dict[str, Any]) -> str:
    colonnes = [c for c in champs if c in CHAMPS_MODIFIABLES] + ["source"]
    valeurs = ", ".join(f"cast(:{c} as uuid)" if c in _UUID else f":{c}" for c in colonnes)
    identifiant = await session.scalar(
        text(
            f"INSERT INTO core.application ({', '.join(colonnes)}) "
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
            f"UPDATE core.application SET {affectations}, maj_le = now() "
            "WHERE id = cast(:id as uuid)"
        ),
        {**{c: champs.get(c) for c in colonnes}, "id": identifiant},
    )


async def supprimer(session: AsyncSession, identifiant: str) -> None:
    await session.execute(
        text("DELETE FROM core.application WHERE id = cast(:id as uuid)"), {"id": identifiant}
    )


# --- Référentiel des éditeurs ----------------------------------------------------------------

TABLE_EDITEUR = "core.editeur_application"


async def lister_editeurs(session: AsyncSession) -> list[RowMapping]:
    lignes = await session.execute(
        text(f"SELECT id::text AS id, libelle, actif FROM {TABLE_EDITEUR} ORDER BY libelle")
    )
    return list(lignes.mappings().all())


async def trouver_ou_creer_editeur(session: AsyncSession, libelle: str) -> str:
    """Identifiant de l'éditeur, créé au besoin. Insensible à la casse et aux espaces."""
    propre = " ".join(libelle.split())
    identifiant = await session.scalar(
        text(f"SELECT id::text FROM {TABLE_EDITEUR} WHERE upper(btrim(libelle)) = upper(:l)"),
        {"l": propre},
    )
    if identifiant is not None:
        return str(identifiant)
    cree = await session.scalar(
        text(f"INSERT INTO {TABLE_EDITEUR} (libelle) VALUES (:l) RETURNING id::text"),
        {"l": propre},
    )
    return str(cree)


async def editeur_utilise(session: AsyncSession, identifiant: str) -> bool:
    """Vrai si au moins une application pointe cet éditeur : on ne le retire pas dans son dos."""
    return bool(
        await session.scalar(
            text("SELECT 1 FROM core.application WHERE editeur_id = cast(:id as uuid) LIMIT 1"),
            {"id": identifiant},
        )
    )


async def supprimer_editeur(session: AsyncSession, identifiant: str) -> bool:
    """Retire un éditeur du référentiel. Renvoie ``False`` s'il n'existait pas."""
    ligne = await session.execute(
        text(f"DELETE FROM {TABLE_EDITEUR} WHERE id = cast(:id as uuid) RETURNING libelle"),
        {"id": identifiant},
    )
    return ligne.first() is not None

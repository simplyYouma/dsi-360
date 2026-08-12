"""Repository de l'inventaire applicatif : applications, éditeurs et responsables."""

import json
from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

#: Rôles de responsabilité sur une application. ADMIN : celui qui en répond. SECOURS : le relais.
ROLE_ADMIN = "ADMIN"
ROLE_SECOURS = "SECOURS"
ROLES = (ROLE_ADMIN, ROLE_SECOURS)


def _responsables_sql(role: str, alias: str) -> str:
    """Sous-requête donnant les responsables d'un rôle, en JSON, dans leur ordre d'affichage.

    Le nom affiché vient du compte quand il y en a un — ainsi la fiche suit le nom de l'agent s'il
    change — et du texte saisi sinon (prestataire, support éditeur, personne sans compte).
    """
    return f"""(
    SELECT coalesce(
      json_agg(json_build_object(
        'utilisateur_id', r.utilisateur_id::text,
        'nom', coalesce(u.prenom || ' ' || u.nom, r.nom_libre)
      ) ORDER BY r.ordre, r.cree_le),
      '[]'::json)
    FROM core.application_responsable r
    LEFT JOIN core.utilisateur u ON u.id = r.utilisateur_id
    WHERE r.application_id = a.id AND r.role = '{role}'
  ) AS {alias}"""


_CHAMPS = f"""
    a.id::text AS id, a.reference, a.nom, a.processus_metier, a.fonctionnalites, a.version,
    a.editeur_id::text AS editeur_id, ed.libelle AS editeur,
    a.hebergement, a.pays_donnees, a.interfacage, a.statut, a.proprietaire,
    a.date_debut, a.date_fin, a.nb_comptes_actifs, a.lien,
    a.serveur_application, a.serveur_base, a.port,
    a.actif, a.source, a.cree_le, a.maj_le,
    {_responsables_sql(ROLE_ADMIN, "administrateurs")},
    {_responsables_sql(ROLE_SECOURS, "administrateurs_secours")}
"""


def responsables(valeur: Any) -> list[dict[str, Any]]:
    """Les responsables d'une ligne, toujours en liste (le pilote peut les rendre en texte)."""
    if isinstance(valeur, str):
        valeur = json.loads(valeur)
    return list(valeur) if isinstance(valeur, list) else []

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
        "actif",
    }
)
_UUID = frozenset({"editeur_id"})

#: Valeur de filtre pour « aucun administrateur désigné ». Un mot-clé plutôt qu'un identifiant :
#: l'absence d'administrateur n'est pas un administrateur particulier.
SANS_ADMINISTRATEUR = "AUCUN"

#: Une application a-t-elle un responsable dont le nom correspond à la recherche ? On cherche
#: indifféremment dans les comptes rattachés et dans les noms saisis à la main : celui qui cherche
#: « Diarra » ne sait pas si Diarra a un compte.
_RESPONSABLE_NOMME = """
    SELECT 1 FROM core.application_responsable rr
    LEFT JOIN core.utilisateur ru ON ru.id = rr.utilisateur_id
    WHERE rr.application_id = a.id
      AND (rr.nom_libre ILIKE :q OR (ru.prenom || ' ' || ru.nom) ILIKE :q)
"""

#: L'application a-t-elle au moins un responsable de ce rôle ?
def _a_un_responsable(role: str) -> str:
    return (
        "EXISTS (SELECT 1 FROM core.application_responsable rr "
        f"WHERE rr.application_id = a.id AND rr.role = '{role}')"
    )


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
            " OR a.proprietaire ILIKE :q OR a.serveur_application ILIKE :q"
            " OR a.serveur_base ILIKE :q OR ed.libelle ILIKE :q"
            f" OR EXISTS ({_RESPONSABLE_NOMME}))"
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
        conditions += f" AND NOT {_a_un_responsable(ROLE_ADMIN)}"
    elif administrateur is not None:
        # Par compte quand l'appelant a choisi un agent, par nom sinon — le front envoie l'un ou
        # l'autre, et l'on ne sait pas d'avance si la personne cherchée a un compte.
        conditions += (
            " AND EXISTS (SELECT 1 FROM core.application_responsable rr "
            " LEFT JOIN core.utilisateur ru ON ru.id = rr.utilisateur_id "
            " WHERE rr.application_id = a.id AND (rr.utilisateur_id::text = :adm_id "
            "   OR rr.nom_libre ILIKE :adm OR (ru.prenom || ' ' || ru.nom) ILIKE :adm))"
        )
        params["adm"] = f"%{administrateur.strip()}%"
        params["adm_id"] = administrateur.strip()
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
                f"count(*) FILTER (WHERE a.actif AND NOT {_a_un_responsable(ROLE_ADMIN)}) "
                "  AS sans_administrateur, "
                f"count(*) FILTER (WHERE a.actif AND NOT {_a_un_responsable(ROLE_SECOURS)}) "
                "  AS sans_secours "
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


async def remplacer_responsables(
    session: AsyncSession, application_id: str, role: str, personnes: list[dict[str, Any]]
) -> None:
    """Pose la liste complète des responsables d'un rôle : ce qui n'y figure plus est retiré.

    Remplacement plutôt qu'ajout/retrait à l'unité : l'écran manipule une liste, et une liste se
    dit en entier. On évite ainsi les états intermédiaires (retiré ici, pas là) sur un aller-retour.
    L'ordre de saisie est conservé — le premier nommé est celui qu'on appelle en premier.
    """
    await session.execute(
        text(
            "DELETE FROM core.application_responsable "
            "WHERE application_id = cast(:id as uuid) AND role = :role"
        ),
        {"id": application_id, "role": role},
    )
    for ordre, personne in enumerate(personnes):
        compte = personne.get("utilisateur_id")
        nom = personne.get("nom")
        if compte is None and not (nom or "").strip():
            continue  # une ligne qui ne désigne personne n'a rien à faire là
        await session.execute(
            text(
                "INSERT INTO core.application_responsable "
                "(application_id, utilisateur_id, nom_libre, role, ordre) "
                "VALUES (cast(:id as uuid), cast(:compte as uuid), :nom, :role, :ordre) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "id": application_id,
                "compte": compte,
                # Le nom libre ne sert que sans compte : sinon il ferait doublon avec l'annuaire,
                # et divergerait le jour où l'agent change de nom.
                "nom": None if compte is not None else (nom or "").strip(),
                "role": role,
                "ordre": ordre,
            },
        )


async def noms_responsables(
    session: AsyncSession, application_id: str, role: str
) -> list[dict[str, Any]]:
    """Les responsables d'un rôle, nommés, dans l'ordre — pour le journal d'audit."""
    lignes = await session.execute(
        text(
            "SELECT coalesce(u.prenom || ' ' || u.nom, r.nom_libre) AS nom "
            "FROM core.application_responsable r "
            "LEFT JOIN core.utilisateur u ON u.id = r.utilisateur_id "
            "WHERE r.application_id = cast(:id as uuid) AND r.role = :role "
            "ORDER BY r.ordre, r.cree_le"
        ),
        {"id": application_id, "role": role},
    )
    return [{"nom": ligne[0]} for ligne in lignes.all()]


async def comptes_existants(session: AsyncSession, identifiants: list[str]) -> set[str]:
    """Ceux de ces identifiants qui désignent vraiment un compte — le serveur fait foi."""
    if not identifiants:
        return set()
    lignes = await session.execute(
        text("SELECT id::text FROM core.utilisateur WHERE id::text = ANY(:ids)"),
        {"ids": identifiants},
    )
    return {ligne[0] for ligne in lignes.all()}


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

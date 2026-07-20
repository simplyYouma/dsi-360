"""Repository des activités (table générique core.activite, filtré par module)."""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain import etats
from dsi360.domain.activite import PREFIXE_REFERENCE

_LISTE_CHAMPS = """
    a.id::text AS id, a.reference, a.module, a.titre, a.statut, a.priorite, a.impact, a.urgence,
    a.sla_prise_en_charge_le, a.sla_resolution_le, a.cree_le, a.resolu_le, a.cloture_le, a.donnees,
    c.libelle AS categorie, a.categorie_id::text AS categorie_id, d.code AS direction,
    r.id::text AS resp_id, r.prenom AS resp_prenom, r.nom AS resp_nom, r.email AS resp_email,
    -- Niveau de support du gestionnaire : le niveau du ticket importé s'en déduit (ADR-0005).
    r.niveau_support AS resp_niveau,
    dem.nom_complet AS demandeur_nom,
    -- Contributeur (au plus un, cf. contrainte d'unicité) : visible en liste sans ouvrir la fiche.
    (SELECT u.prenom || ' ' || u.nom FROM core.activite_acteur aa
     JOIN core.utilisateur u ON u.id = aa.utilisateur_id
     WHERE aa.activite_id = a.id AND aa.role = 'CONTRIBUTEUR' LIMIT 1) AS contributeur,
    (SELECT count(*) FROM core.commentaire cm
     WHERE cm.activite_id = a.id AND cm.tache_id IS NULL) AS nb_commentaires,
    (SELECT count(*) FROM core.commentaire cm
     WHERE cm.activite_id = a.id AND cm.tache_id IS NULL
       AND cm.auteur_id IS DISTINCT FROM cast(:moi as uuid)
       AND NOT EXISTS (SELECT 1 FROM core.commentaire_vue v
                       WHERE v.commentaire_id = cm.id
                         AND v.utilisateur_id = cast(:moi as uuid))) AS nb_non_vus
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


async def par_id(
    session: AsyncSession, module: str, identifiant: str, *, moi: str | None = None
) -> RowMapping | None:
    requete = text(f"SELECT {_LISTE_CHAMPS}, a.description {_BASE} AND a.id::text = :id")
    resultat = await session.execute(
        requete, {"module": module, "id": identifiant, "moi": moi}
    )
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


# Vue de liste -> phases du domaine. Le vocabulaire des URL reste stable ; le sens vient d'`etats`.
_VUES_PHASE: dict[str, tuple[str, ...]] = {
    "en_cours": (etats.EN_COURS,),
    "termines": (etats.TERMINE,),
    "abandonnes": (etats.ABANDONNE,),
}


def _clause_phase(module: str, vue: str | None, params: dict[str, Any]) -> str:
    """Restreint la liste à une phase (en cours / terminés / abandonnés).

    Les statuts concernés sont **déduits** de `domain.etats` : aucune liste n'est écrite ici.
    """
    phases = _VUES_PHASE.get(vue or "")
    if phases is None:
        return ""
    statuts = etats.statuts_de_phase(*phases, module=module)
    if not statuts:
        # Le module n'a aucun statut dans cette phase : la vue est vide, et le dit franchement.
        return " AND false"
    placeholders = ", ".join(f":ph{i}" for i in range(len(statuts)))
    for i, s in enumerate(statuts):
        params[f"ph{i}"] = s
    return f" AND a.statut IN ({placeholders})"


# Le retard est une horloge, pas une phase : il se croise avec n'importe quelle vue. Un ticket
# résolu hors délai reste en retard — c'est même la vraie mesure du non-respect du SLA.
_CLAUSE_RETARD = (
    " AND a.resolu_le IS NULL"
    " AND a.sla_resolution_le IS NOT NULL AND a.sla_resolution_le < now()"
)


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
    dbs: bool = False,
    q: str | None = None,
    etat: str | None = None,
    retard: bool = False,
    moi: str | None = None,
) -> tuple[list[RowMapping], int]:
    params: dict[str, Any] = {"module": module, "moi": moi}
    filtres = ""
    if direction is not None:
        # Une activité sans direction (tickets importés : l'import n'en pose pas) appartient à
        # tout le monde — cohérent avec `_visible`. Sans le OR, elle disparaîtrait de la liste
        # d'un agent non transverse, alors que sa fiche reste ouverte : incohérence.
        filtres += " AND (d.code = :direction OR a.direction_id IS NULL)"
        params["direction"] = direction
    # Chercher, c'est vouloir retrouver un dossier — pas fouiller la vue courante. Une recherche
    # non vide passe donc OUTRE les filtres de la liste (état, statut, personne) : sinon un ticket
    # clôturé reste introuvable tant que la liste affiche « En cours », et l'écran ment par
    # omission. Seul le cloisonnement par direction tient : il ne se contourne jamais.
    recherche = q is not None and q.strip() != ""
    if statut is not None and not recherche:
        filtres += " AND a.statut = :statut"
        params["statut"] = statut
    if responsable_id is not None and not recherche:
        # Filtrer sur une personne, c'est vouloir « ce dont elle s'occupe » : ce qu'elle gère, mais
        # aussi ce à quoi elle contribue. Sans le contributeur, une activité qu'on lui a confiée en
        # renfort disparaîtrait du filtre alors qu'elle est bien dans sa file.
        filtres += (
            " AND (a.responsable_id = cast(:resp as uuid)"
            " OR EXISTS (SELECT 1 FROM core.activite_acteur aa"
            "            WHERE aa.activite_id = a.id AND aa.utilisateur_id = cast(:resp as uuid)"
            "              AND aa.role = 'CONTRIBUTEUR'))"
        )
        params["resp"] = responsable_id
    if non_assigne and not recherche:
        # « Non assigné » = personne, vraiment. `responsable_id IS NULL` ne suffit pas : un ticket
        # confié à DBS n'a pas de compte chez nous, mais il est bel et bien assigné (à eux). Et un
        # ticket où l'un des nôtres contribue n'est pas orphelin non plus. Ne restent que ceux que
        # personne n'a pris : ni compte, ni nom au fichier, ni renfort.
        filtres += (
            " AND a.responsable_id IS NULL"
            " AND nullif(trim(a.donnees->>'gestionnaire'), '') IS NULL"
            " AND NOT EXISTS (SELECT 1 FROM core.activite_acteur aa2"
            "                 WHERE aa2.activite_id = a.id AND aa2.role = 'CONTRIBUTEUR')"
        )
    if dbs and not recherche:
        # Chez DBS : un nom au fichier, aucun compte chez nous (ADR-0005).
        filtres += (
            " AND a.responsable_id IS NULL"
            " AND nullif(trim(a.donnees->>'gestionnaire'), '') IS NOT NULL"
        )
    if recherche and q is not None:
        # Recherche élargie : référence, titre, mais aussi les personnes — gestionnaire (compte DSI
        # ou nom importé), demandeur, et contributeurs. On cherche « qui » autant que « quoi ».
        filtres += (
            " AND (a.reference ILIKE :q OR a.titre ILIKE :q"
            " OR (r.prenom || ' ' || r.nom) ILIKE :q"
            " OR a.donnees->>'gestionnaire' ILIKE :q"
            " OR dem.nom_complet ILIKE :q"
            " OR EXISTS (SELECT 1 FROM core.activite_acteur aa"
            "            JOIN core.utilisateur cu ON cu.id = aa.utilisateur_id"
            "            WHERE aa.activite_id = a.id"
            "              AND (cu.prenom || ' ' || cu.nom) ILIKE :q))"
        )
        params["q"] = f"%{q.strip()}%"
    else:
        filtres += _clause_phase(module, etat, params)
    # Le retard survit à la recherche : c'est un fait, pas une préférence d'affichage.
    if retard:
        filtres += _CLAUSE_RETARD

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


async def compter_etats(
    session: AsyncSession, module: str, *, direction: str | None
) -> dict[str, int]:
    """Comptes par phase pour l'en-tête de liste, plus le retard (qui traverse les phases).

    Les statuts de chaque phase viennent de `domain.etats` : mêmes règles que les filtres, donc
    les compteurs et les listes ne peuvent pas diverger. Respecte le cloisonnement par direction
    de `lister` (une activité sans direction — ticket importé — reste visible par tous).
    """
    params: dict[str, Any] = {"module": module}
    cond = ""
    if direction is not None:
        cond = " AND (d.code = :direction OR a.direction_id IS NULL)"
        params["direction"] = direction

    def _filtre_phase(cle: str, phases: tuple[str, ...]) -> str:
        statuts = etats.statuts_de_phase(*phases, module=module)
        if not statuts:
            return f"0 AS {cle}"
        noms = []
        for i, s in enumerate(statuts):
            nom = f"{cle}{i}"
            params[nom] = s
            noms.append(f":{nom}")
        return f"count(*) FILTER (WHERE a.statut IN ({', '.join(noms)})) AS {cle}"

    colonnes = ", ".join(
        [
            "count(*) AS total",
            _filtre_phase("en_cours", (etats.EN_COURS,)),
            _filtre_phase("termines", (etats.TERMINE,)),
            _filtre_phase("abandonnes", (etats.ABANDONNE,)),
            "count(*) FILTER (WHERE a.resolu_le IS NULL"
            " AND a.sla_resolution_le IS NOT NULL"
            " AND a.sla_resolution_le < now()) AS en_retard",
        ]
    )
    ligne = (
        await session.execute(
            text(
                f"SELECT {colonnes} "
                "FROM core.activite a LEFT JOIN core.direction d ON d.id = a.direction_id "
                f"WHERE a.module = :module{cond}"
            ),
            params,
        )
    ).mappings().one()
    cles = ("total", "en_cours", "termines", "abandonnes", "en_retard")
    return {k: int(ligne[k]) for k in cles}


async def lister_tout(
    session: AsyncSession,
    module: str,
    *,
    direction: str | None,
    limite: int = 5000,
    moi: str | None = None,
) -> list[RowMapping]:
    """Toutes les activités du périmètre (sans pagination) — pour les exports."""
    params: dict[str, Any] = {"module": module, "limite": limite, "moi": moi}
    cond = ""
    if direction is not None:
        # Activité sans direction (tickets importés) = visible par tous (cf. `_visible`).
        cond = " AND (d.code = :direction OR a.direction_id IS NULL)"
        params["direction"] = direction
    lignes = await session.execute(
        text(f"SELECT {_LISTE_CHAMPS} {_BASE}{cond} ORDER BY a.cree_le DESC LIMIT :limite"),
        params,
    )
    return list(lignes.mappings().all())


async def maj_evaluation(
    session: AsyncSession,
    identifiant: str,
    *,
    impact: int,
    urgence: int,
    priorite: int,
    sla_prise_en_charge_le: datetime | None,
    sla_resolution_le: datetime | None,
) -> None:
    """Réévalue impact/urgence/priorité et repositionne les échéances SLA."""
    await session.execute(
        text(
            "UPDATE core.activite SET impact = :i, urgence = :u, priorite = :p, "
            "sla_prise_en_charge_le = :pc, sla_resolution_le = :res WHERE id::text = :id"
        ),
        {
            "id": identifiant, "i": impact, "u": urgence, "p": priorite,
            "pc": sla_prise_en_charge_le, "res": sla_resolution_le,
        },
    )


async def assigner(session: AsyncSession, identifiant: str, responsable_id: str | None) -> None:
    """Affecte (ou retire) le gestionnaire DSI d'une activité."""
    await session.execute(
        text(
            "UPDATE core.activite SET responsable_id = cast(:resp as uuid) WHERE id::text = :id"
        ),
        {"id": identifiant, "resp": responsable_id},
    )


# Acteurs secondaires d'une activité (core.activite_acteur). Rôles : CONTRIBUTEUR (commente/suit)
# et VALIDEUR (approuve). Même câblage, paramétré par le rôle.
async def lister_acteurs(session: AsyncSession, identifiant: str, role: str) -> list[RowMapping]:
    lignes = await session.execute(
        text(
            "SELECT u.id::text AS id, u.prenom, u.nom, u.email, aa.decision "
            "FROM core.activite_acteur aa "
            "JOIN core.utilisateur u ON u.id = aa.utilisateur_id "
            "WHERE aa.activite_id = cast(:id as uuid) AND aa.role = :role "
            "ORDER BY u.prenom, u.nom"
        ),
        {"id": identifiant, "role": role},
    )
    return list(lignes.mappings().all())


async def definir_decision(
    session: AsyncSession, identifiant: str, utilisateur_id: str, decision: str
) -> bool:
    """Enregistre la décision (APPROUVE/REJETE) d'un valideur. False s'il n'est pas valideur."""
    resultat = await session.execute(
        text(
            "UPDATE core.activite_acteur SET decision = :d, decide_le = now() "
            "WHERE activite_id = cast(:aid as uuid) AND utilisateur_id = cast(:uid as uuid) "
            "AND role = 'VALIDEUR' RETURNING utilisateur_id"
        ),
        {"aid": identifiant, "uid": utilisateur_id, "d": decision},
    )
    return resultat.first() is not None


async def ajouter_acteur(
    session: AsyncSession, identifiant: str, utilisateur_id: str, role: str
) -> None:
    """Désigne l'acteur du rôle. Un seul par rôle : nommer quelqu'un d'autre le remplace.

    La décision repart à zéro avec le nouveau valideur — l'avis de son prédécesseur
    ne l'engage pas.
    """
    await session.execute(
        text(
            "INSERT INTO core.activite_acteur (activite_id, utilisateur_id, role) "
            "VALUES (cast(:aid as uuid), cast(:uid as uuid), :role) "
            "ON CONFLICT (activite_id, role) DO UPDATE "
            "SET utilisateur_id = excluded.utilisateur_id, decision = NULL"
        ),
        {"aid": identifiant, "uid": utilisateur_id, "role": role},
    )


async def retirer_acteur(
    session: AsyncSession, identifiant: str, utilisateur_id: str, role: str
) -> None:
    await session.execute(
        text(
            "DELETE FROM core.activite_acteur WHERE activite_id = cast(:aid as uuid) "
            "AND utilisateur_id = cast(:uid as uuid) AND role = :role"
        ),
        {"aid": identifiant, "uid": utilisateur_id, "role": role},
    )


async def lister_contributeurs(session: AsyncSession, identifiant: str) -> list[RowMapping]:
    return await lister_acteurs(session, identifiant, "CONTRIBUTEUR")


async def ajouter_contributeur(
    session: AsyncSession, identifiant: str, utilisateur_id: str
) -> None:
    await ajouter_acteur(session, identifiant, utilisateur_id, "CONTRIBUTEUR")


async def retirer_contributeur(
    session: AsyncSession, identifiant: str, utilisateur_id: str
) -> None:
    await retirer_acteur(session, identifiant, utilisateur_id, "CONTRIBUTEUR")


async def lister_valideurs(session: AsyncSession, identifiant: str) -> list[RowMapping]:
    return await lister_acteurs(session, identifiant, "VALIDEUR")


async def ajouter_valideur(session: AsyncSession, identifiant: str, utilisateur_id: str) -> None:
    await ajouter_acteur(session, identifiant, utilisateur_id, "VALIDEUR")


async def retirer_valideur(
    session: AsyncSession, identifiant: str, utilisateur_id: str
) -> None:
    await retirer_acteur(session, identifiant, utilisateur_id, "VALIDEUR")


async def des_valideurs_ont_decide(session: AsyncSession, identifiant: str) -> bool:
    """Vrai dès qu'au moins un valideur a tranché : la liste des valideurs se fige alors."""
    return (
        await session.scalar(
            text(
                "SELECT 1 FROM core.activite_acteur "
                "WHERE activite_id = cast(:aid as uuid) AND role = 'VALIDEUR' "
                "AND decision IS NOT NULL LIMIT 1"
            ),
            {"aid": identifiant},
        )
        is not None
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

"""Requalification d'un ticket importé : le même ticket a changé de module à la source.

SysAid numérote incidents et demandes dans **la même série**. Requalifier un ticket n'en change ni
le numéro ni le contenu : seul son type bascule. Chez nous, l'unicité porte sur
``(module, source_id)`` — le ticket requalifié entrait donc une seconde fois, sous l'autre module,
et les deux fiches vivaient côte à côte : l'ancienne figée pour toujours au dernier état connu, la
nouvelle sans commentaires, sans pièces jointes, sans histoire. Les statistiques comptaient deux
activités là où il n'y en avait qu'une.

Ce module répare et prévient, en une seule règle : **le numéro du ticket identifie le ticket,
quel que soit le module.** L'import déplace donc la fiche existante au lieu d'en créer une seconde.

Deux situations, et la seconde est celle du parc déjà en production :

1. **Déplacement simple** — la fiche existe sous l'ancien module, rien sous le nouveau. On la
   déplace : elle garde son identifiant, donc ses commentaires, ses pièces jointes, ses
   contributeurs et ses notifications. Seule sa référence change (INC-1234 → DEM-1234).
2. **Fusion** — les deux fiches existent déjà, l'import précédent ayant créé le doublon. On
   rapatrie sur l'ancienne tout ce qui a été ajouté à la main sur la nouvelle, **puis** on
   supprime le doublon. Jamais l'inverse : la suppression est en cascade, supprimer d'abord
   effacerait sans bruit ce que quelqu'un avait écrit (principe n° 4, zéro perte).

On garde la **plus ancienne** fiche, jamais la plus récente : c'est elle que le journal d'audit,
les notifications déjà envoyées et les liens partagés désignent. La plus récente n'apporte que des
données du rapport, que l'upsert réécrit juste après de toute façon.

« La plus ancienne » se lit dans le journal d'audit, à son écriture de CRÉATION — pas dans
`cree_le`, qui porte la date du ticket à la source et vaut donc la même chose sur les deux fiches.
Se fier au module (« celle qui n'est pas dans le module cible est l'originale ») serait faux une
fois sur deux : le doublon peut avoir été créé de l'un OU l'autre côté, selon le sens de la
requalification.
"""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CursorResult, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.activite import reference_ticket
from dsi360.infrastructure import audit

#: Les tickets déjà connus, par numéro de source. Une seule requête : le rapport quotidien compte
#: des milliers de lignes, les interroger une par une multiplierait les allers-retours.
_TICKETS_CONNUS = text(
    "SELECT id::text AS id, module, reference, source_id, antecedents "
    "FROM core.activite WHERE source = 'IMPORT_SD' AND source_id IS NOT NULL"
)

#: Date de naissance de chaque fiche importée, lue dans le journal d'audit. `core.activite.cree_le`
#: ne peut pas servir : c'est la date du ticket À LA SOURCE, identique sur les deux fiches d'un
#: doublon.
_NAISSANCES = text(
    "SELECT module, cible_id, min(horodatage) AS ne_le FROM audit.journal "
    "WHERE action = 'CREATION' AND cible_type IN ('incident', 'demande') "
    "GROUP BY module, cible_id"
)

#: Une fiche sans écriture de création dans le journal n'a pas été créée par l'import : on ne peut
#: pas la dater, et elle ne peut donc pas revendiquer l'antériorité.
_JAMAIS_NEE = datetime.max.replace(tzinfo=UTC)

#: Contenu ajouté à la main sur une fiche, à rapatrier avant toute suppression. Rien ici ne peut
#: entrer en conflit : ces tables n'ont pas d'unicité portant sur `activite_id`.
_RATTACHEMENTS_LIBRES = (
    ("core.commentaire", "commentaires"),
    ("core.document", "documents"),
    ("core.lien", "liens"),
    ("core.note", "notes"),
    ("core.tache", "taches"),
    ("core.jalon", "jalons"),
)


async def index_tickets(session: AsyncSession) -> dict[str, list[dict[str, Any]]]:
    """Numéro de ticket -> fiches qui le portent, tous modules confondus, la plus ancienne d'abord.

    Plus d'une entrée signifie qu'un doublon de requalification traîne encore : c'est exactement
    ce que le prochain import doit résoudre. Deux requêtes seulement : le rapport quotidien compte
    des milliers de lignes, les interroger une par une multiplierait les allers-retours.
    """
    naissances = {
        (r["module"], r["cible_id"]): r["ne_le"]
        for r in (await session.execute(_NAISSANCES)).mappings().all()
    }
    index: dict[str, list[dict[str, Any]]] = {}
    for ligne in (await session.execute(_TICKETS_CONNUS)).mappings().all():
        fiche = dict(ligne)
        fiche["ne_le"] = naissances.get((fiche["module"], fiche["reference"]), _JAMAIS_NEE)
        index.setdefault(str(fiche["source_id"]), []).append(fiche)
    for fiches in index.values():
        fiches.sort(key=lambda f: f["ne_le"])
    return index


async def _rapatrier(session: AsyncSession, du_doublon: str, vers: str) -> dict[str, int]:
    """Déplace vers la fiche conservée tout ce qui a été ajouté à la main sur le doublon."""
    deplaces: dict[str, int] = {}
    for table, nom in _RATTACHEMENTS_LIBRES:
        resultat = await session.execute(
            text(
                f"UPDATE {table} SET activite_id = cast(:vers as uuid) "  # noqa: S608 — liste fermée
                "WHERE activite_id = cast(:source as uuid)"
            ),
            {"vers": vers, "source": du_doublon},
        )
        if isinstance(resultat, CursorResult) and resultat.rowcount:
            deplaces[nom] = resultat.rowcount

    # Contributeurs et valideurs : un seul par rôle et par fiche (ux_activite_acteur_role). Ceux
    # de la fiche conservée l'emportent — c'est elle que l'on garde ; on ne déplace que les rôles
    # qu'elle n'a pas encore. Le reste disparaîtra avec le doublon, et le compte-rendu le dit.
    acteurs = await session.execute(
        text(
            "UPDATE core.activite_acteur a SET activite_id = cast(:vers as uuid) "
            "WHERE a.activite_id = cast(:source as uuid) "
            "  AND NOT EXISTS (SELECT 1 FROM core.activite_acteur b "
            "                  WHERE b.activite_id = cast(:vers as uuid) AND b.role = a.role)"
        ),
        {"vers": vers, "source": du_doublon},
    )
    if isinstance(acteurs, CursorResult) and acteurs.rowcount:
        deplaces["acteurs"] = acteurs.rowcount

    # Notifications : unicité sur (activite_id, type) pour les alertes SLA. Une notification est
    # jetable — on ne déplace que ce qui ne se heurte à rien, le reste part avec le doublon.
    notifs = await session.execute(
        text(
            "UPDATE core.notification n SET activite_id = cast(:vers as uuid) "
            "WHERE n.activite_id = cast(:source as uuid) "
            "  AND NOT EXISTS (SELECT 1 FROM core.notification m "
            "                  WHERE m.activite_id = cast(:vers as uuid) AND m.type = n.type "
            "                    AND m.type IN ('SLA_APPROCHE', 'SLA_DEPASSE'))"
        ),
        {"vers": vers, "source": du_doublon},
    )
    if isinstance(notifs, CursorResult) and notifs.rowcount:
        deplaces["notifications"] = notifs.rowcount
    return deplaces


def _en_clair(deplaces: dict[str, int]) -> str:
    """« 3 commentaires, 1 document » — le journal d'audit ne parle pas en identifiants."""
    if not deplaces:
        return "aucun contenu ajouté à la main"
    return ", ".join(f"{n} {nom}" for nom, n in sorted(deplaces.items()))


async def requalifier(
    session: AsyncSession,
    *,
    fiches: list[dict[str, Any]],
    module_cible: str,
    source_id: str,
    acteur: dict[str, Any],
) -> dict[str, int]:
    """Ramène le ticket `source_id` à une seule fiche, placée dans `module_cible`.

    `fiches` : toutes celles que porte ce numéro, **triées de la plus ancienne à la plus récente**
    par `index_tickets`. Retourne ce qui a été fait : `reclasses` (la fiche a changé de module),
    `doublons_fusionnes` (des fiches en trop ont été absorbées puis supprimées).
    """
    if not fiches:
        return {}

    # La plus ancienne est l'originale : c'est elle que le journal, les notifications déjà parties
    # et les liens partagés désignent. Garder la plus récente changerait l'identifiant de
    # l'activité et les ferait tous pointer dans le vide.
    conservee, *surnumeraires = fiches
    fait: dict[str, int] = {}

    # 1. Les fiches en trop d'abord : l'une d'elles occupe peut-être la référence que la fiche
    #    conservée doit prendre (core.activite.reference est unique), et leur contenu doit être
    #    sauvé AVANT toute suppression — celle-ci est en cascade.
    for surnumeraire in surnumeraires:
        deplaces = await _rapatrier(
            session, du_doublon=str(surnumeraire["id"]), vers=str(conservee["id"])
        )
        await session.execute(
            text("DELETE FROM core.activite WHERE id = cast(:id as uuid)"),
            {"id": str(surnumeraire["id"])},
        )
        fait["doublons_fusionnes"] = fait.get("doublons_fusionnes", 0) + 1
        await audit.consigner(
            session,
            action="FUSION",
            acteur_id=acteur["id"],
            acteur_email=acteur["email"],
            module=module_cible,
            cible_type=module_cible,
            cible_id=reference_ticket(module_cible, source_id),
            ancienne={"fiche_en_double": str(surnumeraire["reference"])},
            nouvelle={
                "conservee": str(conservee["reference"]),
                "repris": _en_clair(deplaces),
                "motif": (
                    "Un import precedent avait cree une seconde fiche pour le meme ticket, "
                    "requalifie a la source. Les deux fiches n'en font plus qu'une."
                ),
            },
        )

    if conservee["module"] == module_cible:
        return fait  # elle était déjà du bon côté : il n'y avait qu'un doublon à absorber

    # 2. La fiche conservée prend sa nouvelle identité, et se souvient de l'ancienne : le journal
    #    est append-only, ses écritures d'avant portent encore l'ancienne référence.
    reference_avant = str(conservee["reference"])
    module_avant = str(conservee["module"])
    reference_apres = reference_ticket(module_cible, source_id)
    antecedents = list(conservee["antecedents"] or [])
    antecedents.append(
        {
            "module": module_avant,
            "reference": reference_avant,
            "le": datetime.now(UTC).isoformat(),
        }
    )
    await session.execute(
        text(
            "UPDATE core.activite "
            # La catégorie appartient à un module (core.categorie est indexée sur (module, code)) :
            # la garder ferait pointer une demande vers une catégorie d'incident. L'upsert qui suit
            # immédiatement pose celle du nouveau module.
            "SET module = :module, reference = :reference, categorie_id = NULL, "
            "    antecedents = cast(:antecedents as jsonb) "
            "WHERE id = cast(:id as uuid)"
        ),
        {
            "module": module_cible,
            "reference": reference_apres,
            "antecedents": json.dumps(antecedents),
            "id": str(conservee["id"]),
        },
    )
    fait["reclasses"] = 1
    await audit.consigner(
        session,
        action="RECLASSEMENT",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=module_cible,
        cible_type=module_cible,
        cible_id=reference_apres,
        ancienne={"module": module_avant, "reference": reference_avant},
        nouvelle={
            "module": module_cible,
            "reference": reference_apres,
            "motif": "Le rapport quotidien classe desormais ce ticket dans un autre module.",
        },
    )
    return fait

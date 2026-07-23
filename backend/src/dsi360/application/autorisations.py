"""Autorisations par activité : qui peut faire quoi, sur *cette* activité.

Deux plans distincts, à ne pas confondre :

1. **L'accès au module** (``core.acces_role``, garde ``exiger_acces``) dit quelles *pages* un profil
   voit. C'est un préalable : sans lui, rien n'est visible.
2. **Le rôle sur l'activité** (ci-dessous) dit ce qu'on peut y *faire*. Il découle de qui est
   responsable, contributeur, valideur, ou assigné d'une de ses tâches.

L'administrateur distribue le travail — il assigne le gestionnaire, fixe l'impact et l'urgence,
désigne contributeurs et valideurs. Les acteurs l'exécutent. Le valideur ne fait que décider, et
l'administrateur ne décide pas à sa place (séparation des tâches).

Ce module est **pur** : ni FastAPI, ni HTTP. Il lève des exceptions de domaine que la couche
interface traduit en codes de statut, comme le fait déjà ``application.activites``.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.config.acces import PROFIL_ADMIN

# Exigences déclarées par une route. Un ensemble se lit comme un « ou ».
ADMIN: Final = "ADMIN"
ACTEUR: Final = "ACTEUR"
VALIDEUR: Final = "VALIDEUR"

# Seul champ d'une tâche que son assigné peut changer : il rend compte de son avancement.
_CHAMP_DE_L_ASSIGNE: Final = "statut"


class AccesRefuse(Exception):
    """L'utilisateur n'a pas le rôle requis sur cette activité."""


class AgentIneligible(Exception):
    """On ne peut désigner qu'un compte actif dont le profil a l'accès au module."""


@dataclass(frozen=True)
class RolesActivite:
    """Rôles d'un utilisateur sur une activité donnée. Cumulables."""

    est_admin: bool = False
    est_responsable: bool = False
    est_contributeur: bool = False
    est_valideur: bool = False
    #: Assigné d'au moins une tâche de l'activité.
    est_assigne: bool = False

    @property
    def est_acteur_travail(self) -> bool:
        """Fait avancer le sujet : transitions, tâches, notes, documents, liens.

        Le contributeur a les droits de travail du gestionnaire, pas ceux d'organisation.
        """
        return self.est_admin or self.est_responsable or self.est_contributeur

    @property
    def est_designe(self) -> bool:
        """Désigné à un titre quelconque sur l'activité (donne la visibilité, cf. `visible`)."""
        return (
            self.est_responsable or self.est_contributeur or self.est_valideur or self.est_assigne
        )


def capacites(
    roles: RolesActivite, *, lecture_seule: bool = False, clos: bool = False
) -> dict[str, bool]:
    """Ce que l'utilisateur peut faire. Source unique : gardes serveur **et** affichage.

    ``lecture_seule`` : incidents et demandes, dont l'état vient de l'import quotidien. On n'y agit
    pas — hormis la désignation de contributeurs par l'administrateur, qui met le ticket dans leur
    file sans leur donner prise dessus (ADR-0005).

    ``clos`` : activité dans un état terminal (clôturé, rejeté, annulé, réalisé…). **Un dossier
    clos reste modifiable** : la DSI corrige régulièrement un dossier après coup — un intitulé
    inexact, un gestionnaire mal renseigné, un bilan qu'on rédige justement une fois la mise en
    production faite. Interdire ces corrections revenait à figer des erreurs. Ce qui protège
    l'information, ce n'est pas le verrou : c'est le journal d'audit, qui garde qui a changé
    quoi et quand (principe n° 4, zéro perte). Deux exceptions demeurent, parce qu'elles
    réécriraient l'histoire plutôt qu'une donnée : une **décision de valideur** déjà rendue ne
    se rejoue pas, et le **statut** d'un état terminal ne se change que par les transitions que
    le domaine autorise (`etats`).
    """
    acteur = roles.est_acteur_travail
    if lecture_seule:
        # Une exception : l'administrateur y désigne des contributeurs, pour que la DSI suive un
        # ticket qu'elle ne traite pas — y compris quand le rapport a mis DBS au gestionnaire.
        # La description reste saisissable par les acteurs (gestionnaire, contributeurs, admin) :
        # le rapport importé n'a pas de colonne description, on ne l'écrase donc jamais (ADR-0005).
        return {
            "peut_assigner": False,
            "peut_evaluer": False,
            "peut_gerer_acteurs": roles.est_admin,
            "peut_travailler": False,
            "peut_decider": False,
            "peut_completer_dossier": False,
            "peut_editer_description": acteur,
        }
    if clos:
        return {
            "peut_assigner": roles.est_admin,
            "peut_evaluer": roles.est_admin,
            "peut_gerer_acteurs": roles.est_admin,
            "peut_travailler": acteur,
            # Une décision rendue ne se rejoue pas : c'est un acte, pas une donnée.
            "peut_decider": False,
            "peut_completer_dossier": acteur,
            "peut_editer_description": False,
        }
    return {
        "peut_assigner": roles.est_admin,
        "peut_evaluer": roles.est_admin,
        "peut_gerer_acteurs": roles.est_admin,
        "peut_travailler": acteur,
        "peut_decider": roles.est_valideur,
        "peut_completer_dossier": acteur,
        # Modules pilotés (changement…) : la description passe par le PATCH principal.
        "peut_editer_description": False,
    }


def satisfait(roles: RolesActivite, requis: set[str]) -> bool:
    """L'utilisateur remplit-il l'une des exigences de la route ?"""
    return (
        (ADMIN in requis and roles.est_admin)
        or (ACTEUR in requis and roles.est_acteur_travail)
        or (VALIDEUR in requis and roles.est_valideur)
    )


def visible(direction: str | None, courant: dict[str, Any], roles: RolesActivite) -> bool:
    """Périmètre : profil transverse, même direction, activité sans direction — ou acteur désigné.

    Un contributeur désigné hors de sa direction doit voir l'activité : sinon la désignation serait
    lettre morte. Il a nécessairement l'accès au module, sans quoi on n'aurait pas pu le désigner.
    """
    if courant["transverse"]:
        return True
    if direction is None or direction == courant["direction"]:
        return True
    return roles.est_designe


def controler_champs_tache(
    roles: RolesActivite, *, assigne_de_la_tache: bool, champs: Iterable[str]
) -> str | None:
    """Renvoie le motif de refus, ou ``None`` si la modification est permise.

    Un acteur de travail modifie tout. L'assigné d'une tâche n'en change que le statut : c'est à
    lui de rendre compte de son avancement, pas de se réassigner ni de repousser son échéance.
    """
    if roles.est_acteur_travail:
        return None
    if not assigne_de_la_tache:
        return "Action réservée au gestionnaire, aux contributeurs et à l'administrateur."
    interdits = sorted(set(champs) - {_CHAMP_DE_L_ASSIGNE})
    if interdits:
        return (
            "Vous êtes assigné à cette tâche : vous n'en changez que le statut "
            f"(champs refusés : {', '.join(interdits)})."
        )
    return None


# --- Accès base ----------------------------------------------------------------------------------

_ROLES = text(
    "SELECT "
    " EXISTS (SELECT 1 FROM core.activite_acteur"
    "         WHERE activite_id = cast(:aid as uuid) AND utilisateur_id = cast(:uid as uuid)"
    "           AND role = 'CONTRIBUTEUR') AS contributeur, "
    " EXISTS (SELECT 1 FROM core.activite_acteur"
    "         WHERE activite_id = cast(:aid as uuid) AND utilisateur_id = cast(:uid as uuid)"
    "           AND role = 'VALIDEUR') AS valideur, "
    " EXISTS (SELECT 1 FROM core.tache"
    "         WHERE activite_id = cast(:aid as uuid) AND assigne_id = cast(:uid as uuid))"
    "         AS assigne"
)

_DESIGNABLE = text(
    "SELECT 1 FROM core.utilisateur u "
    "JOIN core.profil p ON p.id = u.profil_id "
    "JOIN core.acces_role ar ON ar.profil_code = p.code AND ar.acces = :acces "
    "WHERE u.id::text = :id AND u.actif"
)


async def charger_roles(
    session: AsyncSession, activite: RowMapping, courant: dict[str, Any]
) -> RolesActivite:
    """Rôles de l'utilisateur sur l'activité. Une seule requête, jamais de N+1."""
    r = (
        await session.execute(_ROLES, {"aid": activite["id"], "uid": courant["id"]})
    ).mappings().one()
    responsable = activite["resp_id"]
    return RolesActivite(
        est_admin=courant["profil"] == PROFIL_ADMIN,
        est_responsable=responsable is not None and str(responsable) == courant["id"],
        est_contributeur=bool(r["contributeur"]),
        est_valideur=bool(r["valideur"]),
        est_assigne=bool(r["assigne"]),
    )


async def exiger_designable(session: AsyncSession, utilisateur_id: str, acces: str) -> None:
    """Refuse de désigner un compte inactif, ou dont le profil n'a pas accès au module.

    Pour figurer dans la liste, il faut pouvoir ouvrir l'activité. Sans cette règle, on désignerait
    des gens à qui l'écran resterait fermé.
    """
    if await session.scalar(_DESIGNABLE, {"id": utilisateur_id, "acces": acces}) is None:
        raise AgentIneligible(
            "Agent inéligible : compte inactif, ou profil sans accès à ce module."
        )

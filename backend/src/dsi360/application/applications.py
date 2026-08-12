"""Cas d'usage de l'inventaire applicatif : création, modification, retrait d'une application.

Une application se tient comme un équipement du parc : elle n'a ni workflow ni SLA, mais tout ce
qui la concerne est journalisé — c'est la mémoire administrative du patrimoine logiciel. Qui
administrait telle application il y a un an est une question qu'on pose vraiment, en audit comme
au départ d'un collaborateur.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.texte import nom_significatif, phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.repositories import application as repo

MODULE = "applications"
_CIBLE = "application"


def nom_normalise(nom: str | None) -> str | None:
    """Le nom tel qu'il sera écrit en base : espaces condensés, casse d'origine conservée.

    Une seule règle, partagée par l'écriture et par le contrôle d'unicité. Sans cela, le contrôle
    chercherait « generateur   de test » quand l'insertion écrit « generateur de test » : le
    doublon passait au travers et ressortait en erreur d'intégrité.
    Le nom d'un logiciel n'est pas un nom propre : « AFG E-bank (OBDX) » n'est pas
    « Afg E-Bank (Obdx) » — on ne touche donc jamais à sa casse.
    """
    if nom is None:
        return None
    return " ".join(nom.split())


#: Les deux listes de responsables, avec leur rôle en base et leur nom d'écran (pour le journal).
_LISTES_RESPONSABLES = (
    ("administrateurs", repo.ROLE_ADMIN, "administrateurs"),
    ("administrateurs_secours", repo.ROLE_SECOURS, "administrateurs de secours"),
)


async def _ecrire_responsables(
    session: AsyncSession, application_id: str, champs: dict[str, Any]
) -> None:
    """Applique les listes de responsables fournies. Une liste absente = rôle inchangé."""
    for cle, role, _ in _LISTES_RESPONSABLES:
        if cle in champs and champs[cle] is not None:
            await repo.remplacer_responsables(session, application_id, role, champs[cle])


def _noms(personnes: Any) -> str:
    """« Awa Touré · Mady Wague » — le journal nomme les gens, jamais leurs identifiants."""
    if not isinstance(personnes, list) or not personnes:
        return "—"
    return " · ".join(
        str(p.get("nom") or "").strip() for p in personnes if isinstance(p, dict)
    ).strip(" ·") or "—"


async def creer_application(
    session: AsyncSession,
    champs: dict[str, Any],
    acteur: dict[str, Any],
    *,
    source: str = "SAISIE",
) -> str:
    donnees = _nettoyer(champs)
    donnees["source"] = source
    identifiant = await repo.creer(session, donnees)
    await _ecrire_responsables(session, identifiant, champs)
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=MODULE,
        cible_type=_CIBLE,
        cible_id=donnees.get("nom") or identifiant,
        nouvelle={"nom": donnees.get("nom"), "statut": donnees.get("statut")},
    )
    return identifiant


#: Colonnes de référence : dans le journal on consigne le **libellé**, jamais l'identifiant.
#: Un changement d'éditeur (« DBS → ORACLE ») doit se lire, pas se déchiffrer.
_REFERENCES = {
    "editeur_id": (
        "editeur",
        "SELECT libelle FROM core.editeur_application WHERE id = cast(:id as uuid)",
    ),
}


async def _en_libelles(
    session: AsyncSession, avant: dict[str, Any], donnees: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Valeurs anciennes/nouvelles prêtes pour le journal, références traduites en libellés."""
    anciennes: dict[str, Any] = {}
    nouvelles: dict[str, Any] = {}
    for colonne, valeur in donnees.items():
        reference = _REFERENCES.get(colonne)
        if reference is None:
            anciennes[colonne] = _serialisable(avant.get(colonne))
            nouvelles[colonne] = _serialisable(valeur)
            continue
        cle, sql = reference
        anciennes[cle] = avant.get(cle)
        nouvelles[cle] = (
            None if valeur is None else await session.scalar(text(sql), {"id": valeur})
        )
    return anciennes, nouvelles


async def maj_application(
    session: AsyncSession, avant: dict[str, Any], champs: dict[str, Any], acteur: dict[str, Any]
) -> None:
    donnees = _nettoyer({c: v for c, v in champs.items() if c in repo.CHAMPS_MODIFIABLES})
    anciennes, nouvelles = await _en_libelles(session, avant, donnees)

    # Les responsables ne sont pas des colonnes : on les journalise par leurs NOMS, avant/après.
    # « administrateurs : Awa Touré → Awa Touré · Mady Wague » se relit ; une liste d'uuid, non.
    for cle, role, libelle in _LISTES_RESPONSABLES:
        if cle not in champs or champs[cle] is None:
            continue
        anciennes[libelle] = _noms(avant.get(cle))
        await repo.remplacer_responsables(session, avant["id"], role, champs[cle])
        # On relit les noms plutôt que de reprendre ce qui a été envoyé : un compte désigné tire
        # son nom de l'annuaire, que l'écran ne connaît pas forcément à jour.
        nouvelles[libelle] = _noms(await repo.noms_responsables(session, avant["id"], role))

    await repo.maj(session, avant["id"], donnees)
    await audit.consigner(
        session,
        action="MODIFICATION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=MODULE,
        cible_type=_CIBLE,
        cible_id=avant.get("nom") or avant["id"],
        ancienne=anciennes,
        nouvelle=nouvelles,
    )


async def supprimer_application(
    session: AsyncSession, avant: dict[str, Any], acteur: dict[str, Any]
) -> None:
    await repo.supprimer(session, avant["id"])
    await audit.consigner(
        session,
        action="SUPPRESSION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module=MODULE,
        cible_type=_CIBLE,
        cible_id=avant.get("nom") or avant["id"],
        ancienne={"nom": avant.get("nom"), "statut": avant.get("statut")},
    )


#: Champs libres où « N/A », « None » et consorts ne sont pas des valeurs mais des absences.
#: Les garder tels quels ferait passer une application pour administrée par « N/A ».
_TEXTES_LIBRES = (
    "version",
    "proprietaire",
    "serveur_application",
    "serveur_base",
    "port",
    "pays_donnees",
    "lien",
)


def _nettoyer(champs: dict[str, Any]) -> dict[str, Any]:
    """Normalise les saisies libres et écarte les fausses valeurs (« None », « N/A »…)."""
    propre = dict(champs)
    if "nom" in propre:
        propre["nom"] = nom_normalise(propre["nom"])
    for cle in ("processus_metier", "fonctionnalites"):
        if cle in propre:
            propre[cle] = phrase_propre(propre[cle])
    for cle in _TEXTES_LIBRES:
        if cle in propre:
            propre[cle] = nom_significatif(propre[cle])
    return propre


def _serialisable(valeur: Any) -> Any:
    """Le journal d'audit stocke du JSON : les dates et décimaux passent en texte."""
    if valeur is None or isinstance(valeur, str | int | float | bool):
        return valeur
    return str(valeur)

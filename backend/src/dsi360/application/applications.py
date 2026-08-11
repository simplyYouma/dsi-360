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
    donnees = _nettoyer(champs)
    anciennes, nouvelles = await _en_libelles(session, avant, donnees)
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
    "administrateur",
    "administrateur_secours",
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

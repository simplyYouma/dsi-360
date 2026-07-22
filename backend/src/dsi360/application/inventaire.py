"""Cas d'usage de l'inventaire : création, modification, rapprochement du détenteur.

Le détenteur d'un équipement est désigné par un **matricule** dans le fichier source. On le
rapproche d'un compte existant — jamais on n'en crée un : les comptes se créent depuis
l'administration seule, comme pour les gestionnaires de tickets (ADR-0005).
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.texte import nom_significatif, phrase_propre
from dsi360.infrastructure import audit
from dsi360.infrastructure.repositories import equipement as repo


def _norme(valeur: str | None) -> str:
    return "".join((valeur or "").split()).upper()


async def index_matricules(session: AsyncSession) -> dict[str, str]:
    """Matricule normalisé -> identifiant de compte, pour rattacher les détenteurs en masse."""
    lignes = await session.execute(
        text(
            "SELECT id::text, matricule FROM core.utilisateur "
            "WHERE matricule IS NOT NULL AND btrim(matricule) <> ''"
        )
    )
    return {_norme(m): ident for ident, m in lignes.all() if _norme(m)}


def detenteur_pour(cache: dict[str, str], matricule: str | None) -> str | None:
    """Compte correspondant au matricule, ou ``None`` s'il n'est pas des nôtres.

    Le matricule brut reste conservé sur l'équipement : un import ultérieur, ou la saisie du
    matricule sur le compte, permettra le rattachement sans perdre l'information.
    """
    propre = nom_significatif(matricule)
    if propre is None:
        return None
    return cache.get(_norme(propre))


async def creer_equipement(
    session: AsyncSession, champs: dict[str, Any], acteur: dict[str, Any], *, source: str = "SAISIE"
) -> str:
    donnees = _nettoyer(champs)
    donnees["source"] = source
    identifiant = await repo.creer(session, donnees)
    await audit.consigner(
        session,
        action="CREATION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module="inventaire",
        cible_type="equipement",
        cible_id=donnees.get("code_immo") or donnees.get("designation") or identifiant,
        nouvelle={"designation": donnees.get("designation"), "code_immo": donnees.get("code_immo")},
    )
    return identifiant


#: Colonnes de référence : dans le journal, on consigne le **libellé**, jamais l'identifiant.
#: C'est ce qui rend l'acheminement d'un matériel racontable (« Siège → Agence Kayes ») —
#: un uuid dans l'historique ne raconte rien.
_REFERENCES = {
    "emplacement_id": (
        "emplacement",
        "SELECT libelle FROM core.emplacement WHERE id = cast(:id as uuid)",
    ),
    "departement_id": (
        "departement",
        "SELECT libelle FROM core.departement_equipement WHERE id = cast(:id as uuid)",
    ),
    "detenteur_id": (
        "detenteur",
        "SELECT prenom || ' ' || nom FROM core.utilisateur WHERE id = cast(:id as uuid)",
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
        if colonne == "detenteur_id":
            # La ligne chargée porte déjà le nom de l'ancien détenteur (jointure du repository).
            ancien = (
                f"{avant['det_prenom']} {avant['det_nom']}" if avant.get("det_prenom") else None
            )
        else:
            ancien = avant.get(cle)
        nouveau = None if valeur is None else await session.scalar(text(sql), {"id": valeur})
        anciennes[cle] = ancien
        nouvelles[cle] = nouveau
    return anciennes, nouvelles


async def maj_equipement(
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
        module="inventaire",
        cible_type="equipement",
        cible_id=avant.get("code_immo") or avant.get("designation") or avant["id"],
        ancienne=anciennes,
        nouvelle=nouvelles,
    )


async def supprimer_equipement(
    session: AsyncSession, avant: dict[str, Any], acteur: dict[str, Any]
) -> None:
    await repo.supprimer(session, avant["id"])
    await audit.consigner(
        session,
        action="SUPPRESSION",
        acteur_id=acteur["id"],
        acteur_email=acteur["email"],
        module="inventaire",
        cible_type="equipement",
        cible_id=avant.get("code_immo") or avant.get("designation") or avant["id"],
        ancienne={"designation": avant.get("designation"), "code_immo": avant.get("code_immo")},
    )


def _nettoyer(champs: dict[str, Any]) -> dict[str, Any]:
    """Normalise les saisies libres et écarte les fausses valeurs (« None », « N/A »…)."""
    propre = dict(champs)
    if "designation" in propre:
        propre["designation"] = phrase_propre(propre["designation"])
    for texte in ("code_immo", "numero_serie", "modele", "matricule_brut"):
        if texte in propre:
            valeur = nom_significatif(propre[texte])
            propre[texte] = valeur.upper() if texte == "code_immo" and valeur else valeur
    return propre


def _serialisable(valeur: Any) -> Any:
    """Le journal d'audit stocke du JSON : les dates et décimaux passent en texte."""
    if valeur is None or isinstance(valeur, str | int | float | bool):
        return valeur
    return str(valeur)

"""Journal d'audit append-only et chaîné par empreinte. Cf. docs/04-SECURITY §3.

Chaque entrée enchaîne l'empreinte de la précédente : toute altération ultérieure devient
détectable. L'e-mail de l'acteur est figé à l'écriture (il survit à la suppression du compte).
"""

import contextvars
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Adresse IP de la requête courante, posée par le middleware HTTP (cf. interface/app.py) et lue
# automatiquement par consigner() : évite d'injecter Request dans chaque endpoint d'écriture.
_adresse_ip_courante: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "adresse_ip_courante", default=None
)


def definir_adresse_ip(ip: str | None) -> None:
    _adresse_ip_courante.set(ip)


_DERNIER = text("SELECT hash_courant FROM audit.journal ORDER BY id DESC LIMIT 1")

# Verrou de sérialisation de l'écriture du journal (clé arbitraire, propre à ce verrou).
_VERROU_CHAINE = text("SELECT pg_advisory_xact_lock(872361)")

# Le journal est append-only : quand un ticket est requalifie (incident -> demande), ses ecritures
# d'avant gardent l'ancien module et l'ancienne reference. Interroger la seule identite courante
# ferait repartir l'historique de la fiche a zero — une perte silencieuse. On interroge donc
# l'identite courante ET toutes les precedentes, que la fiche memorise (`antecedents`).
def _identites(
    module: str, reference: str, antecedents: Sequence[Any] | None
) -> list[dict[str, str]]:
    """Identites successives du dossier, la courante d'abord : [{module, reference}, ...]."""
    vues = {(module, reference)}
    couples = [{"module": module, "reference": reference}]
    for a in antecedents or []:
        cle = (str(a.get("module", "")), str(a.get("reference", "")))
        if all(cle) and cle not in vues:
            vues.add(cle)
            couples.append({"module": cle[0], "reference": cle[1]})
    return couples


def _ou_identites(couples: Sequence[dict[str, str]]) -> tuple[str, dict[str, str]]:
    """Clause SQL « (module, cible_id) parmi ces couples », et ses parametres nommes."""
    morceaux = []
    parametres: dict[str, str] = {}
    for i, c in enumerate(couples):
        morceaux.append(f"(module = :module{i} AND cible_id = :reference{i})")
        parametres[f"module{i}"] = c["module"]
        parametres[f"reference{i}"] = c["reference"]
    return "(" + " OR ".join(morceaux) + ")", parametres


def _historique_sql(couples: Sequence[dict[str, str]]) -> tuple[Any, dict[str, str]]:
    ou, parametres = _ou_identites(couples)
    return (
        text(
            "SELECT nouvelle_valeur->>'statut' AS statut, horodatage, acteur_email "
            "FROM audit.journal "
            f"WHERE {ou} "
            "AND action IN ('CREATION', 'TRANSITION') AND nouvelle_valeur->>'statut' IS NOT NULL "
            "ORDER BY id"
        ),
        parametres,
    )


#: Horodatage de la DERNIÈRE transition de chaque dossier d'un module, en une seule requête.
#: L'export a besoin de la date de fin de milliers de dossiers : la lire fiche par fiche
#: (`historique_statuts`) aurait fait autant d'allers-retours que de lignes.
_DERNIERES_TRANSITIONS = text(
    "SELECT cible_id, max(horodatage) AS fin FROM audit.journal "
    "WHERE module = :module AND action IN ('CREATION', 'TRANSITION') "
    "  AND nouvelle_valeur->>'statut' IS NOT NULL "
    "GROUP BY cible_id"
)


async def dernieres_transitions(session: AsyncSession, module: str) -> dict[str, datetime]:
    """Référence -> horodatage de sa dernière transition de statut, pour tout un module.

    Sert à dater la fin des dossiers que leur statut ne date pas : « Résolu » et « Clôturé »
    posent un `resolu_le` / `cloture_le`, mais « Réalisé », « Maîtrisé » ou « Rejeté » n'en posent
    aucun — sans le journal, leur retard à l'arrivée serait incalculable.
    """
    resultat = await session.execute(_DERNIERES_TRANSITIONS, {"module": module})
    return {r["cible_id"]: r["fin"] for r in resultat.mappings().all()}


async def historique_statuts(
    session: AsyncSession, module: str, reference: str,
    antecedents: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    """Parcours réel des statuts d'une activité, reconstitué depuis le journal d'audit.

    `antecedents` : identités précédentes après requalification — sans elles, l'historique d'un
    ticket passé d'incident à demande commencerait au jour du changement.
    """
    requete, parametres = _historique_sql(_identites(module, reference, antecedents))
    resultat = await session.execute(requete, parametres)
    return [
        {"statut": r["statut"], "horodatage": r["horodatage"], "acteur": r["acteur_email"]}
        for r in resultat.mappings().all()
    ]


# TOUT ce qui a touché le dossier — pas seulement les statuts : assignations, valideurs,
# contributeurs, échéances, **liens et pièces jointes**… La fiche doit pouvoir tout raconter
# (zéro perte, principe n° 4).
#
# Liens et documents sont journalisés sous leur propre `cible_type` ('lien', 'document') — sinon
# ils n'apparaissaient pas dans l'historique. Leur `cible_id` est la référence du dossier, ou
# « référence/nom-du-fichier » pour un document : on accepte donc l'égalité ET le préfixe.
def _journal_complet_sql(couples: Sequence[dict[str, str]]) -> tuple[Any, dict[str, str]]:
    morceaux = []
    parametres: dict[str, str] = {}
    for i, c in enumerate(couples):
        morceaux.append(
            f"(module = :module{i} AND cible_type IN (:module{i}, 'lien', 'document') "
            f" AND (cible_id = :reference{i} OR cible_id LIKE :prefixe{i}))"
        )
        parametres[f"module{i}"] = c["module"]
        parametres[f"reference{i}"] = c["reference"]
        parametres[f"prefixe{i}"] = f"{c['reference']}/%"
    return (
        text(
            "SELECT action, horodatage, acteur_email AS acteur, cible_type, cible_id, "
            "ancienne_valeur AS anciennes, nouvelle_valeur AS nouvelles "
            "FROM audit.journal "
            f"WHERE ({' OR '.join(morceaux)}) "
            "ORDER BY id DESC LIMIT :limite"
        ),
        parametres,
    )


async def journal_complet(
    session: AsyncSession, module: str, reference: str, limite: int = 25,
    antecedents: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    """Dernières écritures du journal sur ce dossier, brutes — l'appelant les rend lisibles.

    `antecedents` : identités précédentes après requalification (cf. `historique_statuts`).
    """
    requete, parametres = _journal_complet_sql(_identites(module, reference, antecedents))
    resultat = await session.execute(requete, {**parametres, "limite": limite})
    return [dict(r) for r in resultat.mappings().all()]

def _serialiser(valeurs: dict[str, Any] | None) -> str | None:
    """Journalise une valeur quelle qu'elle soit.

    ``default=str`` rend lisibles les dates et les UUID, que ``json.dumps`` refuse. Sans lui, poser
    une échéance sur une tâche faisait échouer la requête entière : le journal ne doit jamais faire
    tomber l'action qu'il enregistre.
    """
    if valeurs is None:
        return None
    return json.dumps(valeurs, ensure_ascii=False, sort_keys=True, default=str)


_INSERT = text(
    "INSERT INTO audit.journal "
    "(horodatage, acteur_id, acteur_email, module, action, cible_type, cible_id, "
    " ancienne_valeur, nouvelle_valeur, adresse_ip, hash_precedent, hash_courant) "
    "VALUES (:horodatage, cast(:acteur_id as uuid), :acteur_email, :module, :action, "
    " :cible_type, :cible_id, cast(:ancienne as jsonb), cast(:nouvelle as jsonb), "
    " cast(:adresse_ip as inet), :hash_precedent, :hash_courant)"
)


def _empreinte(parties: list[str]) -> str:
    return hashlib.sha256("|".join(parties).encode("utf-8")).hexdigest()


async def consigner(
    session: AsyncSession,
    *,
    action: str,
    acteur_id: str | None = None,
    acteur_email: str | None = None,
    module: str | None = None,
    cible_type: str | None = None,
    cible_id: str | None = None,
    ancienne: dict[str, Any] | None = None,
    nouvelle: dict[str, Any] | None = None,
    adresse_ip: str | None = None,
) -> None:
    # Repli sur l'IP de la requête courante (contextvar) si l'appelant ne la fournit pas.
    if adresse_ip is None:
        adresse_ip = _adresse_ip_courante.get()
    # Verrou tenu jusqu'au commit : deux écritures concurrentes ne peuvent plus lire le même hash
    # précédent et forker la chaîne. Sérialise le seul couple lecture-du-dernier + insertion.
    await session.execute(_VERROU_CHAINE)
    precedent = await session.scalar(_DERNIER)
    horodatage = datetime.now(UTC)
    av = _serialiser(ancienne)
    nv = _serialiser(nouvelle)
    hash_courant = _empreinte(
        [
            precedent or "",
            horodatage.isoformat(),
            acteur_email or "",
            module or "",
            action,
            cible_type or "",
            cible_id or "",
            av or "",
            nv or "",
            adresse_ip or "",
        ]
    )
    await session.execute(
        _INSERT,
        {
            "horodatage": horodatage,
            "acteur_id": acteur_id,
            "acteur_email": acteur_email,
            "module": module,
            "action": action,
            "cible_type": cible_type,
            "cible_id": cible_id,
            "ancienne": av,
            "nouvelle": nv,
            "adresse_ip": adresse_ip,
            "hash_precedent": precedent,
            "hash_courant": hash_courant,
        },
    )
    await session.commit()

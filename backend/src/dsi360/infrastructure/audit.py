"""Journal d'audit append-only et chaîné par empreinte. Cf. docs/04-SECURITY §3.

Chaque entrée enchaîne l'empreinte de la précédente : toute altération ultérieure devient
détectable. L'e-mail de l'acteur est figé à l'écriture (il survit à la suppression du compte).
"""

import contextvars
import hashlib
import json
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

_HISTORIQUE = text(
    "SELECT nouvelle_valeur->>'statut' AS statut, horodatage, acteur_email "
    "FROM audit.journal "
    "WHERE module = :module AND cible_id = :reference "
    "AND action IN ('CREATION', 'TRANSITION') AND nouvelle_valeur->>'statut' IS NOT NULL "
    "ORDER BY id"
)


async def historique_statuts(
    session: AsyncSession, module: str, reference: str
) -> list[dict[str, Any]]:
    """Parcours réel des statuts d'une activité, reconstitué depuis le journal d'audit."""
    resultat = await session.execute(_HISTORIQUE, {"module": module, "reference": reference})
    return [
        {"statut": r["statut"], "horodatage": r["horodatage"], "acteur": r["acteur_email"]}
        for r in resultat.mappings().all()
    ]

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

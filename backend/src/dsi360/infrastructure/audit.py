"""Journal d'audit append-only et chaîné par empreinte. Cf. docs/04-SECURITY §3.

Chaque entrée enchaîne l'empreinte de la précédente : toute altération ultérieure devient
détectable. L'e-mail de l'acteur est figé à l'écriture (il survit à la suppression du compte).
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_DERNIER = text("SELECT hash_courant FROM audit.journal ORDER BY id DESC LIMIT 1")

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
    precedent = await session.scalar(_DERNIER)
    horodatage = datetime.now(UTC)
    av = json.dumps(ancienne, ensure_ascii=False, sort_keys=True) if ancienne is not None else None
    nv = json.dumps(nouvelle, ensure_ascii=False, sort_keys=True) if nouvelle is not None else None
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

"""Écriture du cycle de revue dans `donnees` : fusion des clés à poser, effacement des orphelines.

La *logique* (que poser, qu'effacer) vit dans ``domain.revue.calculer_planification`` — pure et
testée. Ici, la seule I/O : appliquer le résultat à la ligne d'activité, en une requête.
"""

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dsi360.domain.revue import CLES_REVUE


async def ecrire_revue(
    session: AsyncSession, ident: str, fragment: dict[str, object], a_effacer: list[str]
) -> None:
    """Fusionne `fragment` dans `donnees` après avoir retiré `a_effacer` — en une seule écriture.

    Les clés à effacer proviennent d'une liste figée (``CLES_REVUE``), jamais d'une entrée externe :
    l'interpolation dans le SQL est donc sûre. On valide néanmoins l'appartenance par prudence.
    """
    inconnues = [c for c in a_effacer if c not in CLES_REVUE]
    if inconnues:  # garde-fou : ne jamais interpoler une clé non prévue
        raise ValueError(f"Clés de revue inattendues : {inconnues}")
    retraits = "".join(f" - '{c}'" for c in a_effacer)
    await session.execute(
        text(
            f"UPDATE core.activite SET donnees = (donnees{retraits}) || cast(:f as jsonb) "
            "WHERE id = cast(:id as uuid)"
        ),
        {"id": ident, "f": json.dumps(fragment)},
    )

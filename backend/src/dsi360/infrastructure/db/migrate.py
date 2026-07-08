"""Runner de migrations SQL. Applique en ordre les fichiers de db/migrations non encore appliqués.

Utilise asyncpg en direct : la méthode ``execute`` sans paramètre passe par le protocole simple,
qui accepte plusieurs instructions dans un même fichier (contrairement aux requêtes préparées).
Lancement : ``python -m dsi360.infrastructure.db.migrate``.
"""

import asyncio
from pathlib import Path

import asyncpg

from dsi360.config import get_settings

_SUIVI = """
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    nom text PRIMARY KEY,
    applique_le timestamptz NOT NULL DEFAULT now()
)
"""


def _dsn() -> str:
    # asyncpg veut une DSN sans le dialecte SQLAlchemy "+asyncpg".
    return get_settings().database_url.replace("+asyncpg", "")


async def appliquer(*, silencieux: bool = False) -> int:
    """Applique les migrations en attente (idempotent). Retourne le nombre appliqué.

    Un verrou d'avis PostgreSQL sérialise les exécutions concurrentes (deux démarrages simultanés).
    """
    dossier = Path(get_settings().migrations_dir)
    fichiers = sorted(dossier.glob("*.sql"))
    conn = await asyncpg.connect(_dsn())
    try:
        # Verrou global : évite qu'un second process applique les mêmes migrations en même temps.
        await conn.execute("SELECT pg_advisory_lock(872360)")
        await conn.execute(_SUIVI)
        deja = {r["nom"] for r in await conn.fetch("SELECT nom FROM public.schema_migrations")}
        nouveaux = [f for f in fichiers if f.name not in deja]
        if not nouveaux:
            if not silencieux:
                print("Aucune migration à appliquer.")
            return 0
        for f in nouveaux:
            async with conn.transaction():
                await conn.execute(f.read_text(encoding="utf-8"))
                await conn.execute("INSERT INTO public.schema_migrations(nom) VALUES ($1)", f.name)
            print(f"Appliqué : {f.name}")
        return len(nouveaux)
    finally:
        await conn.execute("SELECT pg_advisory_unlock(872360)")
        await conn.close()


if __name__ == "__main__":
    asyncio.run(appliquer())

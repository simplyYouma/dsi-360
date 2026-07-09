"""Harnais des tests d'intégration : base dédiée, isolation par transaction, client HTTP.

Trois garanties, dans cet ordre d'importance :

1. **Jamais la base de développement.** La DSN est dérivée en suffixant « _test », et un garde-fou
   refuse de démarrer si le nom de base ne finit pas par ``_test``. Provisionner la base une fois :
   ``psql -U postgres -f infra/local/provisionner-db-test.sql``.
2. **Aucune fuite entre tests.** Chaque test s'exécute dans une transaction ouverte par le harnais
   et annulée à la fin. Les ``commit()`` de l'application (l'audit en fait un) tombent sur un
   SAVEPOINT : ils sont visibles pendant le test, effacés après.
3. **Aucun effet de bord au démarrage.** Migrations et ordonnanceur SLA sont désactivés côté app
   (le harnais applique les migrations lui-même, une fois).

Les variables d'environnement sont posées **avant** tout import de ``dsi360`` : la configuration
est mise en cache dès l'import et l'app est construite au chargement du module.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

_RACINE = Path(__file__).resolve().parents[2]


def _dsn_de_test() -> str:
    """DSN de la base de test, dérivée de celle de dev en suffixant « _test »."""
    url = os.environ.get("DSI360_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DSI360_DATABASE_URL absente. Charge la configuration avant pytest :\n"
            "    . infra\\local\\env.ps1"
        )
    prefixe, _, base = url.rpartition("/")
    if not base.endswith("_test"):
        url = f"{prefixe}/{base}_test"
    # Garde-fou : on n'exécute jamais la suite sur autre chose qu'une base « _test ».
    if not url.rpartition("/")[2].endswith("_test"):
        raise RuntimeError(f"Base de test attendue (suffixe _test), obtenue : {url}")
    return url


os.environ["DSI360_DATABASE_URL"] = _dsn_de_test()
os.environ.setdefault("DSI360_MIGRATIONS_DIR", str(_RACINE / "db" / "migrations"))
os.environ["DSI360_ENVIRONNEMENT"] = "dev"
os.environ["DSI360_MIGRER_AU_DEMARRAGE"] = "false"  # le harnais s'en charge, une seule fois
os.environ["DSI360_SLA_SCAN_INTERVALLE_S"] = "0"  # pas d'ordonnanceur pendant les tests
os.environ["DSI360_SERVIR_FRONTEND"] = "false"
os.environ.setdefault("DSI360_JWT_SECRET_KEY", "secret-de-test-sans-valeur")
os.environ.setdefault("DSI360_SEED_ADMIN_EMAIL", "admin@afgbank.ml")
os.environ.setdefault("DSI360_SEED_ADMIN_PASSWORD", "MotDePasseDeTest1")

import asyncpg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from dsi360.config import get_settings  # noqa: E402

# La configuration est mémoïsée dès sa première lecture : si un autre module l'a déjà chargée,
# elle porterait la DSN de développement. On la relit avec l'environnement posé ci-dessus.
get_settings.cache_clear()

from dsi360.infrastructure.db import session_scope  # noqa: E402
from dsi360.infrastructure.db.migrate import appliquer  # noqa: E402
from dsi360.infrastructure.db.seed import seed  # noqa: E402
from dsi360.infrastructure.securite import creer_jeton, hacher_mot_de_passe  # noqa: E402
from dsi360.interface.app import app  # noqa: E402

# Garde-fou ultime : jamais de suite de tests sur autre chose qu'une base « _test ».
assert get_settings().database_url.rpartition("/")[2].endswith("_test")


@pytest.fixture(scope="session", autouse=True)
def base_prete() -> Iterator[None]:
    """Applique migrations et seed une fois pour toute la suite (hors transaction de test)."""

    async def _preparer() -> None:
        await appliquer(silencieux=True)
        await seed()

    try:
        asyncio.run(_preparer())
    except asyncpg.InvalidCatalogNameError as exc:  # base de test absente
        pytest.exit(
            "La base de test n'existe pas. Provisionne-la une fois, en superuser :\n"
            '    & "C:\\Program Files\\PostgreSQL\\17\\bin\\psql.exe" -U postgres '
            "-f infra\\local\\provisionner-db-test.sql\n"
            f"({exc})",
            returncode=1,
        )
    yield


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Session liée à une transaction annulée en fin de test.

    ``join_transaction_mode="create_savepoint"`` : les ``commit()`` de l'application libèrent un
    SAVEPOINT au lieu de valider la transaction externe, que l'on annule ensuite.
    NullPool : chaque test a sa propre boucle asyncio, aucune connexion n'est réutilisée.
    """
    moteur = create_async_engine(get_settings().database_url, poolclass=NullPool)
    async with moteur.connect() as connexion:
        await connexion.begin()
        s = AsyncSession(bind=connexion, join_transaction_mode="create_savepoint")
        try:
            yield s
        finally:
            await s.close()
            await connexion.rollback()
    await moteur.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Client HTTP sur l'app ASGI, partageant la transaction du test.

    Pas de `lifespan` déclenché par ASGITransport : ni migrations, ni ordonnanceur.
    """

    async def _session_de_test() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[session_scope] = _session_de_test
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c
    app.dependency_overrides.clear()


# --- Fabriques ---------------------------------------------------------------------------------

MOT_DE_PASSE = "MotDePasseDeTest1"

# Profil métier par défaut des comptes de test : non transverse, tout l'opérationnel (ADR-0003).
PROFIL_METIER = "SUPPORT_APP_HELPDESK"


async def creer_direction(session: AsyncSession, *, code: str, libelle: str | None = None) -> None:
    """Crée une direction le temps du test.

    Le référentiel n'en contient plus qu'une (DSI, ADR-0003 §2), mais le cloisonnement reste
    implémenté : on le prouve en fabriquant une seconde direction, effacée avec la transaction.
    """
    from sqlalchemy import text

    await session.execute(
        text(
            "INSERT INTO core.direction (code, libelle) VALUES (:code, :libelle) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        {"code": code, "libelle": libelle or f"Direction {code}"},
    )
    await session.commit()


async def creer_utilisateur(
    session: AsyncSession,
    *,
    email: str,
    profil: str = PROFIL_METIER,
    direction: str = "DSI",
    actif: bool = True,
    expire_le: Any = None,
    mot_de_passe: str = MOT_DE_PASSE,
) -> str:
    """Insère un utilisateur et renvoie son identifiant."""
    from sqlalchemy import text

    ident = await session.scalar(
        text(
            "INSERT INTO core.utilisateur "
            "(email, nom, prenom, profil_id, direction_id, source_auth, mot_de_passe_hash, "
            " doit_changer_mdp, actif, expire_le) "
            "SELECT :email, 'Nom', 'Prenom', p.id, d.id, 'LOCAL', :hash, false, :actif, :expire "
            "FROM core.profil p, core.direction d "
            "WHERE p.code = :profil AND d.code = :direction "
            "RETURNING id::text"
        ),
        {
            "email": email,
            "hash": hacher_mot_de_passe(mot_de_passe),
            "actif": actif,
            "expire": expire_le,
            "profil": profil,
            "direction": direction,
        },
    )
    if ident is None:
        raise AssertionError(f"Profil {profil} ou direction {direction} absent du seed.")
    await session.commit()
    return str(ident)


def entetes(utilisateur_id: str) -> dict[str, str]:
    """En-tête Authorization porteur d'un jeton d'accès valide pour cet utilisateur."""
    return {"Authorization": f"Bearer {creer_jeton(utilisateur_id, 'acces')}"}
